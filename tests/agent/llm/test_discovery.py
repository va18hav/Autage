"""Unit tests for live model discovery (services/agent/llm/discovery.py)."""

import pytest

import services.agent.llm.discovery as disc
from services.agent.llm.discovery import (
    DiscoveryError,
    _cache_key,
    _tier_for,
    invalidate,
    list_models_live,
)
from services.agent.llm.registry import PROVIDERS


# ── Tier heuristic ────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "model_id,expected",
    [
        ("claude-haiku-5-5", "fast"),
        ("gemini-3.5-flash-lite", "fast"),
        ("gpt-6-luna", "fast"),
        ("gpt-6-astra", "frontier"),
        ("gemini-4-argon", "frontier"),
        ("claude-opus-5-5", "frontier"),
        ("claude-sonnet-5-5", "balanced"),
        ("qwen3:8b", "balanced"),
    ],
)
def test_tier_for(model_id, expected):
    assert _tier_for(model_id) == expected


# ── Provider fetchers (with faked HTTP) ───────────────────────────────────────

@pytest.mark.anyio
async def test_fetch_anthropic_maps_display_name_and_paginates(monkeypatch):
    pages = [
        {"data": [{"id": "claude-haiku-5-5", "display_name": "Claude Haiku 5.5"}],
         "has_more": True, "last_id": "claude-haiku-5-5"},
        {"data": [{"id": "claude-opus-5-5", "display_name": "Claude Opus 5.5"}],
         "has_more": False},
    ]

    def fake_http(url, headers=None, timeout=15):
        return pages.pop(0)

    monkeypatch.setattr(disc, "_http_get_json", fake_http)
    models = disc._fetch_anthropic({"api_key": "k"})
    assert [m.id for m in models] == ["claude-haiku-5-5", "claude-opus-5-5"]
    assert models[0].label == "Claude Haiku 5.5"


def test_fetch_openai_filters_non_chat_models(monkeypatch):
    body = {"data": [
        {"id": "gpt-6-luna"},
        {"id": "text-embedding-3-large"},
        {"id": "whisper-2"},
        {"id": "dall-e-4"},
        {"id": "gpt-realtime-2.1"},
        {"id": "gpt-6-astra"},
    ]}
    monkeypatch.setattr(disc, "_http_get_json", lambda *a, **k: body)
    models = disc._fetch_openai({"api_key": "k"})
    assert [m.id for m in models] == ["gpt-6-astra", "gpt-6-luna"]


def test_fetch_google_requires_generate_content(monkeypatch):
    body = {"models": [
        {"name": "models/gemini-3.8-flash", "displayName": "Gemini 3.8 Flash",
         "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/text-embedding-004",
         "supportedGenerationMethods": ["embedContent"]},
        {"name": "models/gemini-4-argon", "displayName": "Gemini 4 Argon"},
    ]}
    monkeypatch.setattr(disc, "_http_get_json", lambda *a, **k: body)
    models = disc._fetch_google({"api_key": "k"})
    assert [m.id for m in models] == ["gemini-3.8-flash", "gemini-4-argon"]


def test_fetch_openrouter_drops_variants_and_maps_label(monkeypatch):
    body = {"data": [
        {"id": "vendor/thing:batch", "name": "Vendor: Thing"},
        {"id": "vendor/thing", "name": "Vendor: Thing 2"},
        {"id": "anthropic/claude-sonnet-5.5", "name": "Anthropic: Claude Sonnet 5.5"},
    ]}
    monkeypatch.setattr(disc, "_http_get_json", lambda *a, **k: body)
    models = disc._fetch_openrouter(None)
    assert [m.id for m in models] == ["anthropic/claude-sonnet-5.5", "vendor/thing"]
    assert models[0].label == "Claude Sonnet 5.5"


def test_fetch_ollama_uses_base_url(monkeypatch):
    seen_urls = []

    def fake_http(url, headers=None, timeout=15):
        seen_urls.append(url)
        return {"models": [{"name": "llama3.2"}]}

    monkeypatch.setattr(disc, "_http_get_json", fake_http)
    models = disc._fetch_ollama({"base_url": "http://192.168.1.5:11434/"})
    assert [m.id for m in models] == ["llama3.2"]
    assert seen_urls == ["http://192.168.1.5:11434/api/tags"]


# ── Cache behavior ────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_list_models_live_caches_and_bypasses(monkeypatch):
    invalidate(None)
    spec = PROVIDERS["anthropic"]
    calls = []

    def fake_fetch(credential):
        calls.append(credential)
        return [disc.ModelSpec("m1", "M1", "balanced")]

    monkeypatch.setitem(disc._FETCHERS, "anthropic", fake_fetch)

    cred = {"api_key": "k1"}
    first = await list_models_live(spec, cred)
    second = await list_models_live(spec, cred)
    assert first is second
    assert len(calls) == 1  # served from cache

    fresh = await list_models_live(spec, cred, force_refresh=True)
    assert fresh[0].id == "m1"
    assert len(calls) == 2  # force_refresh bypassed the cache

    # Rotating the credential changes the cache key → fresh fetch
    invalidate("anthropic")
    await list_models_live(spec, {"api_key": "k2"})
    assert len(calls) == 3


@pytest.mark.anyio
async def test_list_models_live_raises_on_empty(monkeypatch):
    invalidate(None)
    spec = PROVIDERS["openrouter"]

    def empty(_cred):
        return []

    monkeypatch.setitem(disc._FETCHERS, "openrouter", empty)
    with pytest.raises(DiscoveryError):
        await list_models_live(spec, None)


def test_invalidate_only_touches_target_provider():
    disc._cache[_cache_key("openai", {"api_key": "a"})] = (0, [])
    disc._cache[_cache_key("google", {"api_key": "b"})] = (0, [])
    invalidate("openai")
    remaining = [k for k in disc._cache if k.startswith("google:")]
    assert len(remaining) == 1
    invalidate(None)
    assert disc._cache == {}
