import json
from warnings import warn

from cryptography.fernet import Fernet

from services.config import settings


class SecretDecryptionError(RuntimeError):
    """Raised when an encrypted payload cannot be decrypted (e.g. the
    master key changed since the credential was saved)."""


_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    """Instantiate (and memoize) the Fernet cipher from the master key."""
    global _fernet
    if _fernet is None:
        master_key = (settings.AUTAGE_SECRET_KEY or "").strip()
        if not master_key:
            warn(
                "AUTAGE_SECRET_KEY is not set — using an ephemeral key. Credentials "
                "saved now will NOT decrypt after a restart. Generate one with: "
                'uv run python -c "from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())" and add it to .env',
                stacklevel=3,
            )
            master_key = Fernet.generate_key().decode()
        _fernet = Fernet(master_key.encode())
    return _fernet


def encrypt_payload(payload: dict) -> str:
    """Serialize and Fernet-encrypt a credential payload. Returns ciphertext text."""
    return _get_fernet().encrypt(json.dumps(payload).encode()).decode()
