from uuid import UUID

import pytest

from services.db.models.incident import IncidentStatus
from services.http.verify_webhook import compute_hmac_signature
from services.secrets.store import SecretStore


@pytest.mark.anyio
async def test_webhook_requires_a_configured_secret(api_client):
    body = b'{"source":"datadog","service":"auth-service"}'

    response = await api_client.post("/webhooks/alert", content=body)

    assert response.status_code == 401
    assert "secret not configured" in response.json()["detail"]


@pytest.mark.anyio
async def test_webhook_rejects_missing_or_invalid_signature(api_env, api_client):
    db_secret = "whsec_custom_db_secret_for_signature_test"
    await SecretStore.save("webhook_secret", {"secret": db_secret}, "whsec_…_test")
    body = b'{"source":"datadog","service":"auth-service"}'

    no_sig = await api_client.post("/webhooks/alert", content=body)
    assert no_sig.status_code == 401
    assert no_sig.json()["detail"] == "Invalid webhook signature"

    bad_sig = await api_client.post(
        "/webhooks/alert",
        content=body,
        headers={"X-Hub-Signature-256": "sha256=invalid"},
    )
    assert bad_sig.status_code == 401
    assert bad_sig.json()["detail"] == "Invalid webhook signature"


@pytest.mark.anyio
async def test_webhook_rejects_malformed_json(api_env, api_client):
    db_secret = "whsec_custom_db_secret_for_malformed_json"
    await SecretStore.save("webhook_secret", {"secret": db_secret}, "whsec_…_json")

    raw_bad = b"{malformed-json"
    sig = compute_hmac_signature(raw_bad, db_secret)

    res = await api_client.post(
        "/webhooks/alert",
        content=raw_bad,
        headers={"X-Hub-Signature-256": f"sha256={sig}"},
    )
    assert res.status_code == 400
    assert "valid JSON" in res.json()["detail"]


@pytest.mark.anyio
async def test_webhook_requires_db_secret_and_active_deduplication(api_env, api_client):
    session, pool = api_env

    # Store the webhook secret in the DB credential store
    db_secret = "whsec_custom_db_secret_999"
    await SecretStore.save("webhook_secret", {"secret": db_secret}, "whsec_…_999")

    raw_body = b'{"source":"prometheus","alertname":"KubePodOOMKilled","pod":"api-0"}'
    sig = compute_hmac_signature(raw_body, db_secret)

    # 1. First webhook creates PENDING incident and enqueues ARQ job
    first = await api_client.post(
        "/webhooks/alert",
        content=raw_body,
        headers={"X-Hub-Signature-256": f"sha256={sig}"},
    )
    assert first.status_code == 202
    first_id = first.json()["incident_id"]
    assert len(pool.enqueued) == 1
    assert pool.enqueued[0] == ("run_agent_task", first_id, f"incident:{first_id}")

    # 2. Identical webhook while first incident is still PENDING is deduplicated
    dup = await api_client.post(
        "/webhooks/alert",
        content=raw_body,
        headers={"X-Hub-Signature-256": f"sha256={sig}"},
    )
    assert dup.status_code == 202
    assert dup.json()["message"] == "Incident already exists"
    assert dup.json()["incident_id"] == first_id
    assert len(pool.enqueued) == 1

    # 3. Once the incident is marked COMPLETED, a recurring alert creates a fresh incident
    session.incidents[UUID(first_id)].status = IncidentStatus.COMPLETED
    recur = await api_client.post(
        "/webhooks/alert",
        content=raw_body,
        headers={"X-Hub-Signature-256": f"sha256={sig}"},
    )
    assert recur.status_code == 202
    assert recur.json()["incident_id"] != first_id
    assert len(pool.enqueued) == 2
