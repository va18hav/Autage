from services.secrets.crypto import _decrypt_payload, encrypt_payload

def test_encrypt_and_decrypt_payload_roundtrip():
    payload = {"api_key": "sk-live-987654", "base_url": "https://api.openai.com/v1"}
    ciphertext = encrypt_payload(payload)

    assert isinstance(ciphertext, str)
    assert "sk-live-987654" not in ciphertext
    assert _decrypt_payload(ciphertext) == payload


def test_decrypt_payload_handles_none_and_empty():
    assert _decrypt_payload(None) is None
    assert _decrypt_payload("") is None
