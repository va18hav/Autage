
from cryptography.fernet import Fernet



class SecretDecryptionError(RuntimeError):
    """Raised when an encrypted payload cannot be decrypted (e.g. the
    master key changed since the credential was saved)."""


_fernet: Fernet | None = None
