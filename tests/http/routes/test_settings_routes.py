import pytest

import services.http.routes.settings as settings_routes_mod
from services.http.schemas.settings import (
    TestCredentialResponse as CredentialTestResponse,
)


@pytest.mark.anyio
async def test_provider_catalog_and_llm_step_settings(authed_client):
    # 1. Provider catalog lists all 5 providers and 4 pipeline steps
    cat_res = await authed_client.get("/settings/providers")
    assert cat_res.status_code == 200
    provider_ids = {p["id"] for p in cat_res.json()["providers"]}
    assert provider_ids == {"google", "openai", "anthropic", "openrouter", "ollama"}
    assert len(cat_res.json()["steps"]) == 4

    # 2. Empty payload or duplicate step keys rejected with 400
    assert (await authed_client.put("/settings/llm", json=[])).status_code == 400
    dup_steps = await authed_client.put(
        "/settings/llm",
        json=[
            {"step_key": "triage", "provider_id": "openai", "model_id": "gpt-6-luna"},
            {"step_key": "triage", "provider_id": "google", "model_id": "gemini-3.6-flash"},
        ],
    )
    assert dup_steps.status_code == 400

    # 3. Unknown provider or unknown model rejected with 400
    assert (
        await authed_client.put(
            "/settings/llm",
            json=[{"step_key": "triage", "provider_id": "unknown", "model_id": "m"}],
        )
    ).status_code == 400
    assert (
        await authed_client.put(
            "/settings/llm",
            json=[{"step_key": "triage", "provider_id": "openai", "model_id": "bad"}],
        )
    ).status_code == 400

    # 4. Valid step configuration saved and reset
    put_res = await authed_client.put(
        "/settings/llm",
        json=[
            {
                "step_key": "triage",
                "provider_id": "anthropic",
                "model_id": "claude-sonnet-5-5",
                "temperature": 0.1,
            }
        ],
    )
    assert put_res.status_code == 200
    triage_step = next(s for s in put_res.json()["steps"] if s["step_key"] == "triage")
    assert triage_step["provider_id"] == "anthropic"
    assert triage_step["is_default"] is False

    del_res = await authed_client.delete("/settings/llm/triage")
    assert del_res.status_code == 204

    # Unknown step key on reset returns 404
    assert (await authed_client.delete("/settings/llm/nonexistent")).status_code == 404


@pytest.mark.anyio
async def test_live_model_discovery_paths(authed_client, monkeypatch):
    from services.agent.llm.discovery import DiscoveryError
    from services.agent.llm.registry import ModelSpec

    # Seed an openai credential so discovery paths are reachable
    await authed_client.put(
        "/settings/credentials/openai", json={"fields": {"api_key": "sk-live-1234567890"}}
    )

    live_only = [ModelSpec("super-model-oct-2026", "Super Model", "balanced")]

    # 1. Catalog with a working discovery: models_source=live, static list replaced
    async def fake_live(spec, payload, *, force_refresh=False):
        return live_only if spec.id == "openai" else list(spec.models)

    monkeypatch.setattr(settings_routes_mod.model_discovery, "list_models_live", fake_live)
    cat = (await authed_client.get("/settings/providers")).json()
    openai_entry = next(p for p in cat["providers"] if p["id"] == "openai")
    assert openai_entry["models_source"] == "live"
    assert [m["id"] for m in openai_entry["models"]] == ["super-model-oct-2026"]
    google_entry = next(p for p in cat["providers"] if p["id"] == "google")
    assert google_entry["models_source"] == "static"

    # 2. PUT accepts a live-only model id
    put_live = await authed_client.put(
        "/settings/llm",
        json=[{"step_key": "triage", "provider_id": "openai", "model_id": "super-model-oct-2026"}],
    )
    assert put_live.status_code == 200

    # 3. Discovery fails at validation time → permissive (saved without 400)
    async def broken(spec, payload, *, force_refresh=False):
        raise DiscoveryError("HTTP 500")

    monkeypatch.setattr(settings_routes_mod.model_discovery, "list_models_live", broken)
    put_fallback = await authed_client.put(
        "/settings/llm",
        json=[{"step_key": "diagnostics", "provider_id": "openai", "model_id": "whatever-model"}],
    )
    assert put_fallback.status_code == 200

    # 4. Credential test endpoint = discovery-only probe (no token cost)
    monkeypatch.setattr(
        settings_routes_mod.model_discovery,
        "list_models_live",
        fake_live,
    )
    test_ok = await authed_client.post(
        "/settings/credentials/openai/test",
        json={"fields": {"api_key": "sk-live-1234567890"}},
    )
    body = test_ok.json()
    assert test_ok.status_code == 200
    assert body["ok"] is True
    assert "models available" in body["message"]

    # 5. Credential test failure surfaces as ok=False with diagnosis
    monkeypatch.setattr(
        settings_routes_mod.model_discovery,
        "list_models_live",
        broken,
    )
    test_bad = await authed_client.post(
        "/settings/credentials/openai/test",
        json={"fields": {"api_key": "sk-live-1234567890"}},
    )
    bad_body = test_bad.json()
    assert test_bad.status_code == 200
    assert bad_body["ok"] is False
    assert "openai" == bad_body["provider"]


@pytest.mark.anyio
async def test_credentials_webhook_secret_and_kubernetes_settings(authed_client, monkeypatch):
    # 1. Upsert provider credential + masked preview
    cred_res = await authed_client.put(
        "/settings/credentials/openai",
        json={"fields": {"api_key": "sk-proj-1234567890abcdef"}},
    )
    assert cred_res.status_code == 200
    assert cred_res.json()["preview"] == "sk-…cdef"

    # Missing required field -> 400; unknown provider -> 400
    assert (
        await authed_client.put("/settings/credentials/openai", json={"fields": {}})
    ).status_code == 400
    assert (
        await authed_client.put("/settings/credentials/unknown", json={"fields": {"api_key": "x"}})
    ).status_code == 400

    # List and delete credential
    list_creds = await authed_client.get("/settings/credentials")
    assert len(list_creds.json()) == 1
    assert (await authed_client.delete("/settings/credentials/openai")).status_code == 204
    assert (await authed_client.delete("/settings/credentials/openai")).status_code == 404

    # 2. Webhook secret lifecycle
    wh_initial = await authed_client.get("/settings/webhook")
    assert wh_initial.json()["configured"] is False

    wh_gen = await authed_client.post("/settings/webhook/secret")
    assert wh_gen.status_code == 200
    assert wh_gen.json()["configured"] is True
    assert wh_gen.json()["secret"].startswith("whsec_")

    # 3. Kubernetes configuration lifecycle + connectivity test
    k8s_init = await authed_client.get("/settings/kubernetes")
    assert k8s_init.json()["configured"] is False
    assert k8s_init.json()["ca_configured"] is False

    CA = "-----BEGIN CERTIFICATE-----\nMiIC\n-----END CERTIFICATE-----\n"

    # Missing CA certificate -> rejected (TLS verification is mandatory)
    k8s_no_ca = await authed_client.put(
        "/settings/kubernetes",
        json={
            "server_url": "https://k8s-api.prod.internal:6443/",
            "token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.serviceaccount",
        },
    )
    assert k8s_no_ca.status_code == 422

    k8s_put = await authed_client.put(
        "/settings/kubernetes",
        json={
            "server_url": "https://k8s-api.prod.internal:6443/",
            "token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.serviceaccount",
            "ca_cert": CA,
        },
    )
    assert k8s_put.status_code == 200
    assert k8s_put.json()["configured"] is True
    assert k8s_put.json()["ca_configured"] is True
    assert k8s_put.json()["server_url"] == "https://k8s-api.prod.internal:6443"

    # Probe itself rejects http:// URLs and malformed CA certs (real probe,
    # no network call needed for these invalid inputs)
    http_probe = await authed_client.post(
        "/settings/kubernetes/test",
        json={"server_url": "http://k8s-api.prod.internal:6443", "token": "tokentokentoken", "ca_cert": CA},
    )
    assert http_probe.status_code == 200
    assert http_probe.json()["ok"] is False
    assert "https://" in http_probe.json()["message"]

    bad_ca_probe = await authed_client.post(
        "/settings/kubernetes/test",
        json={
            "server_url": "https://k8s-api.prod.internal:6443",
            "token": "tokentokentoken",
            "ca_cert": "definitely-not-a-certificate-but-long-enough-to-pass-length-validation",
        },
    )
    assert bad_ca_probe.status_code == 200
    assert bad_ca_probe.json()["ok"] is False
    assert "CA certificate" in bad_ca_probe.json()["message"]

    monkeypatch.setattr(
        settings_routes_mod,
        "_probe_k8s_api",
        lambda url, tok, ca: CredentialTestResponse(
            ok=True,
            provider="kubernetes",
            model=url,
            message="Connected to Kubernetes API server with verified TLS certificate.",
        ),
    )
    k8s_test = await authed_client.post(
        "/settings/kubernetes/test",
        json={
            "server_url": "https://k8s-api.prod.internal:6443",
            "token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.serviceaccount",
            "ca_cert": CA,
        },
    )
    assert k8s_test.status_code == 200
    assert k8s_test.json()["ok"] is True

    assert (await authed_client.delete("/settings/kubernetes")).status_code == 204
    assert (await authed_client.delete("/settings/kubernetes")).status_code == 404
