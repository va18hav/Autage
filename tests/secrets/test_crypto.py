import warnings
import pytest
from cryptography.fernet import Fernet

import services.secrets.crypto as crypto_mod
from services.secrets.crypto import (
    SecretDecryptionError,
    _decrypt_payload,
    decrypt_payload,
    encrypt_payload,
)


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


@pytest.mark.anyio
async def test_decrypt_payload_decorator_sync_and_async():
    expected = {"secret": "whsec_abc123"}
    ciphertext = encrypt_payload(expected)

    @decrypt_payload
    def fetch_sync():
        return ciphertext

    @decrypt_payload
    async def fetch_async():
        return ciphertext

    assert fetch_sync() == expected
    assert await fetch_async() == expected


def test_ephemeral_fernet_key_warns_when_master_key_unset(monkeypatch):
    monkeypatch.setattr(crypto_mod, "_fernet", None)
    monkeypatch.setattr(crypto_mod.settings, "AUTAGE_SECRET_KEY", "")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        f = crypto_mod._get_fernet()
        assert isinstance(f, Fernet)
        assert any("AUTAGE_SECRET_KEY is not set" in str(w.message) for w in caught)

    monkeypatch.setattr(crypto_mod, "_fernet", None)
