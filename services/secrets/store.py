
from services.db.database import async_session_factory
from services.db.models.credentials import Credential
from services.secrets.crypto import decrypt_payload


class SecretStore:
    """The single entry point for reading and writing integration credentials.

    Payloads are always Fernet-encrypted at rest. Reads go through the
    `decrypt_payload` decorator, so callers receive plain dicts and no other
    module needs decryption logic.
    """

    @staticmethod
    @decrypt_payload
    async def fetch_payload(purpose: str) -> str | None:
        """Fetch the ciphertext for `purpose` — decrypted to a dict by the
        `decrypt_payload` decorator before it reaches the caller."""
        async with async_session_factory() as db:
            credential = await db.get(Credential, purpose)
            return credential.encrypted_payload if credential else None
