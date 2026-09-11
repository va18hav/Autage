import pytest
import services.secrets.crypto as crypto_mod
from services.secrets.crypto import SecretDecryptionError, _decrypt_payload, encrypt_payload

def test_encrypt_and_decrypt_payload_roundtrip():
    payload = {"api_key": "sk-live-987654", "base_url": "https://api.openai.com/v1"}
    ciphertext = encrypt_payload(payload)

    assert isinstance(ciphertext, str)
    assert "sk-live-987654" not in ciphertext
    assert _decrypt_payload(ciphertext) == payload


def test_decrypt_payload_handles_none_and_empty():
    assert _decrypt_payload(None) is None
    assert _decrypt_payload("") is None


def test_decrypt_payload_raises_on_invalid_token():
    with pytest.raises(SecretDecryptionError, match="Failed to decrypt"):
        _decrypt_payload("not-a-valid-fernet-token")


def test_decrypt_payload_raises_on_non_json_plaintext():
    cipher = crypto_mod._get_fernet()
    bad_ciphertext = cipher.encrypt(b"not-valid-json-{").decode()

    with pytest.raises(SecretDecryptionError, match="not a valid JSON document"):
        _decrypt_payload(bad_ciphertext)
