import pytest

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
