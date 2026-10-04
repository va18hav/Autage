import pytest
from services.config import settings
from services.http.verify_webhook import compute_hmac_signature

@pytest.mark.anyio
async def test_webhook_rejects_missing_or_invalid_signature(api_client):
    body = b'{"source":"datadog","service":"auth-service"}'

    no_sig = await api_client.post("/webhooks/alert", content=body)
    assert no_sig.status_code == 401

    bad_sig = await api_client.post(
        "/webhooks/alert",
        content=body,
        headers={"X-Hub-Signature-256": "sha256=invalid"},
    )
    assert bad_sig.status_code == 401


@pytest.mark.anyio
async def test_webhook_rejects_malformed_json(api_client):
    raw_bad = b"{malformed-json"
    sig = compute_hmac_signature(raw_bad, settings.WEBHOOK_SECRET)

    res = await api_client.post(
        "/webhooks/alert",
        content=raw_bad,
        headers={"X-Hub-Signature-256": f"sha256={sig}"},
    )
    assert res.status_code == 400
    assert "valid JSON" in res.json()["detail"]
