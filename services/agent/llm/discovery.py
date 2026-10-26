"""Live model discovery: ask each provider what models it currently serves.

Replaces hard-coded model lists as the primary source in the UI. The static
registry catalog stays as fallback (used before a key exists or when a
provider's listing endpoint fails).

Discovery uses plain HTTP GET endpoints (no SDKs) so all five providers share
one code path. Results are cached in memory with a short TTL, keyed by
provider + credential, and invalidated whenever a credential is saved/deleted
so "enter key → models appear" is always fresh.
"""

import asyncio
import hashlib
import json
import time
import urllib.request
import urllib.error
from typing import Any, Optional

from services.agent.llm.registry import ModelSpec, ProviderSpec

_CACHE_TTL_SECONDS = 15 * 60
_cache: dict[str, tuple[float, list[ModelSpec]]] = {}


class DiscoveryError(Exception):
    """Raised when a provider's model list could not be fetched."""


# ── Low-level HTTP ────────────────────────────────────────────────────────────

def _http_get_json(url: str, headers: Optional[dict] = None, timeout: int = 15) -> Any:
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            pass
        raise DiscoveryError(f"HTTP {exc.code} from {url.split('?')[0]} {body}") from exc
    except Exception as exc:
        raise DiscoveryError(f"{exc.__class__.__name__}: {exc}") from exc


# ── Tier + label heuristics ───────────────────────────────────────────────────

_FRONTIER_MARKERS = ("opus", "fable", "pro", "astra", "argon", "frontier", "max")
_FAST_MARKERS = ("haiku", "flash-lite", "mini", "nano", "lite", "luna", "small")


def _tier_for(model_id: str) -> str:
    low = model_id.lower()
    if any(m in low for m in _FRONTIER_MARKERS):
        return "frontier"
    if any(m in low for m in _FAST_MARKERS):
        return "fast"
    return "balanced"


def _label_for(provider_id: str, model_id: str, name: Optional[str] = None) -> str:
    if name and name.strip() and name.strip() != model_id:
        # OpenRouter names look like "Vendor: Model Name"
        return name.split(":", 1)[1].strip() if ": " in name else name.strip()
    return model_id


# ── Per-provider fetchers (each returns chat-capable ModelSpecs) ──────────────

def _fetch_anthropic(credential: dict) -> list[ModelSpec]:
    api_key = credential.get("api_key", "")
    models: list[ModelSpec] = []
    after_id: Optional[str] = None
    while len(models) < 500:  # hard cap so a paging bug can't loop forever
        url = "https://api.anthropic.com/v1/models?limit=1000"
        if after_id:
            url += f"&after_id={after_id}"
        body = _http_get_json(url, headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        })
        for item in body.get("data", []):
            mid = item.get("id", "")
            if mid:
                models.append(ModelSpec(
                    id=mid, label=item.get("display_name") or mid,
                    tier=_tier_for(mid),
                ))
        if not body.get("has_more"):
            break
        after_id = body.get("last_id")
        if not after_id:
            break
    return models


def _fetch_openai(credential: dict) -> list[ModelSpec]:
    body = _http_get_json(
        "https://api.openai.com/v1/models",
        headers={"Authorization": f"Bearer {credential.get('api_key', '')}"},
    )
    exclude = (
        "embedding", "whisper", "tts", "dall-e", "moderation", "audio",
        "transcribe", "image", "realtime", "davinci", "babbage", "codex",
        "computer-use", "search", "guard", "rosalind", "voice",
    )
    models = []
    seen = set()
    for item in body.get("data", []):
        mid = item.get("id", "")
        if not mid or mid in seen or any(m in mid.lower() for m in exclude):
            continue
        seen.add(mid)
        models.append(ModelSpec(id=mid, label=mid, tier=_tier_for(mid)))
    return sorted(models, key=lambda m: m.label.lower())


def _fetch_google(credential: dict) -> list[ModelSpec]:
    api_key = credential.get("api_key", "")
    models: list[ModelSpec] = []
    page_token: Optional[str] = None
    while len(models) < 500:
        url = "https://generativelanguage.googleapis.com/v1beta/models?pageSize=200"
        if page_token:
            url += f"&pageToken={page_token}"
        body = _http_get_json(url, headers={"x-goog-api-key": api_key})
        for item in body.get("models", []):
            methods = item.get("supportedGenerationMethods") or []
            if methods and "generateContent" not in methods:
                continue
            full_name = item.get("name", "")  # e.g. "models/gemini-3.8-flash"
            mid = full_name.removeprefix("models/")
            # Chat/text models only — specialty agents (antigravity, deep
            # research) aren't selectable pipeline models.
            if mid and mid.startswith(("gemini", "gemma", "learnlm")):
                models.append(ModelSpec(
                    id=mid, label=item.get("displayName") or mid,
                    tier=_tier_for(mid),
                ))
        page_token = body.get("nextPageToken")
        if not page_token:
            break
    return sorted(models, key=lambda m: m.label.lower())


_OPENROUTER_DROP_SUFFIXES = (
    ":batch", ":floor", ":thinking", ":nitro", ":extended", ":online", ":free-routes",
)


def _fetch_openrouter(credential: dict) -> list[ModelSpec]:
    body = _http_get_json("https://openrouter.ai/api/v1/models")
    models = []
    for item in body.get("data", []):
        mid = item.get("id", "")
        if not mid or any(mid.endswith(s) for s in _OPENROUTER_DROP_SUFFIXES):
            continue
        models.append(ModelSpec(
            id=mid, label=_label_for("openrouter", mid, item.get("name")),
            tier=_tier_for(mid),
        ))
    return sorted(models, key=lambda m: m.label.lower())


def _fetch_ollama(credential: Optional[dict]) -> list[ModelSpec]:
    base_url = ((credential or {}).get("base_url") or "http://localhost:11434").rstrip("/")
    body = _http_get_json(f"{base_url}/api/tags")
    models = []
    for item in body.get("models", []):
        mid = item.get("name") or item.get("model") or ""
        if mid:
            models.append(ModelSpec(id=mid, label=mid, tier=_tier_for(mid)))
    return sorted(models, key=lambda m: m.label.lower())


# ── Dispatch + cache ──────────────────────────────────────────────────────────

_FETCHERS = {
    "anthropic": _fetch_anthropic,
    "openai": _fetch_openai,
    "google": _fetch_google,
    "openrouter": lambda _cred: _fetch_openrouter(None),
    "ollama": _fetch_ollama,
}


def _cache_key(provider_id: str, credential: Optional[dict]) -> str:
    payload = json.dumps(credential or {}, sort_keys=True)
    return f"{provider_id}:{hashlib.sha256(payload.encode()).hexdigest()}"


async def list_models_live(
    spec: ProviderSpec,
    credential: Optional[dict],
    *,
    force_refresh: bool = False,
) -> list[ModelSpec]:
    """Fetch the provider's current chat models (cached by default).

    Raises DiscoveryError on failure — callers decide how to degrade.
    """
    fetcher = _FETCHERS.get(spec.id)
    if fetcher is None:
        raise DiscoveryError(f"No model-listing endpoint for provider '{spec.id}'")

    key = _cache_key(spec.id, credential)
    if not force_refresh:
        cached = _cache.get(key)
        if cached is not None and time.monotonic() - cached[0] < _CACHE_TTL_SECONDS:
            return cached[1]

    # The provider calls are blocking urllib requests — keep them off the
    # event loop.
    models = await asyncio.to_thread(fetcher, credential)
    if not models:
        raise DiscoveryError(f"Provider '{spec.id}' returned an empty model list")
    _cache[key] = (time.monotonic(), models)
    return models


def invalidate(provider_id: Optional[str] = None) -> None:
    """Drop cached discoveries — called when a credential is saved or deleted."""
    if provider_id is None:
        _cache.clear()
    else:
        for key in [k for k in _cache if k.startswith(f"{provider_id}:")]:
            _cache.pop(key, None)
