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
            {"step_key": "triage", "provider_id": "openai", "model_id": "gpt-4o-mini"},
            {"step_key": "triage", "provider_id": "google", "model_id": "gemini-2.5-flash"},
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
                "model_id": "claude-sonnet-4",
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

    k8s_put = await authed_client.put(
        "/settings/kubernetes",
        json={
            "server_url": "https://k8s-api.prod.internal:6443/",
            "token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.serviceaccount",
        },
    )
    assert k8s_put.status_code == 200
    assert k8s_put.json()["configured"] is True
    assert k8s_put.json()["server_url"] == "https://k8s-api.prod.internal:6443"

    monkeypatch.setattr(
        settings_routes_mod,
        "_probe_k8s_api",
        lambda url, tok: CredentialTestResponse(
            ok=True,
            provider="kubernetes",
            model=url,
            message="Connected to Kubernetes API server.",
        ),
    )
    k8s_test = await authed_client.post(
        "/settings/kubernetes/test",
        json={
            "server_url": "https://k8s-api.prod.internal:6443",
            "token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.serviceaccount",
        },
    )
    assert k8s_test.status_code == 200
    assert k8s_test.json()["ok"] is True

    assert (await authed_client.delete("/settings/kubernetes")).status_code == 204
    assert (await authed_client.delete("/settings/kubernetes")).status_code == 404
