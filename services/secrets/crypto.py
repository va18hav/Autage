import json
from functools import wraps
from inspect import iscoroutinefunction

from cryptography.fernet import Fernet, InvalidToken

from services.config import settings


class SecretDecryptionError(RuntimeError):
    """Raised when an encrypted payload cannot be decrypted (e.g. the
    master key changed since the credential was saved)."""


_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    """Instantiate (and memoize) the Fernet cipher from the master key."""
    global _fernet
    if _fernet is None:
        master_key = settings.AUTAGE_SECRET_KEY.strip()
        if not master_key:
            raise RuntimeError(
                "AUTAGE_SECRET_KEY is required to encrypt stored credentials."
            )
        _fernet = Fernet(master_key.encode())
    return _fernet


def encrypt_payload(payload: dict) -> str:
    """Serialize and Fernet-encrypt a credential payload. Returns ciphertext text."""
    return _get_fernet().encrypt(json.dumps(payload).encode()).decode()


def _decrypt_payload(ciphertext: str | None) -> dict | None:
    """Turn stored ciphertext into its plaintext payload dict."""
    if not ciphertext:
        return None

    try:
        plaintext = _get_fernet().decrypt(ciphertext.encode())
        return json.loads(plaintext)
    except InvalidToken as exc:
        raise SecretDecryptionError(
            "Failed to decrypt a stored credential — the encryption key "
            "(AUTAGE_SECRET_KEY) differs from the one used to save it. "
            "Re-enter the affected API keys in Settings."
        ) from exc
    except json.JSONDecodeError as exc:
        raise SecretDecryptionError(
            "Stored credential payload is not a valid JSON document."
        ) from exc


def decrypt_payload(func):
    """Decorator: decrypts the payload returned by the wrapped callable.

    Apply this to any function whose return value is a Fernet ciphertext
    (e.g. a DAO method that fetches an encrypted credential). Callers receive
    the decrypted dict (or None) and never touch decryption logic themselves.

    Works on both sync and async callables.
    """

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        return _decrypt_payload(await func(*args, **kwargs))

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        return _decrypt_payload(func(*args, **kwargs))

    return async_wrapper if iscoroutinefunction(func) else sync_wrapper
