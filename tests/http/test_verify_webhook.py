from services.http.verify_webhook import compute_hmac_signature, verify_webhook_signature

def test_compute_and_verify_webhook_signature():
    payload = b'{"source":"datadog","metric":"container.memory.usage","value":0.99}'
    secret = "whsec_live_secret_key"
    digest = compute_hmac_signature(payload, secret)

    assert len(digest) == 64
    assert verify_webhook_signature(payload, f"sha256={digest}", secret) is True
    assert verify_webhook_signature(payload, digest, secret) is True
