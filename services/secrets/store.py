from sqlalchemy import select

from services.db.database import async_session_factory
from services.db.models.credentials import Credential
from services.secrets.crypto import encrypt_payload, decrypt_payload


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

    @staticmethod
    async def save(purpose: str, payload: dict, preview: str | None) -> Credential:
        """Upsert a credential: encrypt the payload, keep a masked preview."""
        ciphertext = encrypt_payload(payload)
        async with async_session_factory() as db:
            credential = await db.get(Credential, purpose)
            if credential is None:
                credential = Credential(purpose=purpose)
                db.add(credential)
            credential.encrypted_payload = ciphertext
            credential.preview = preview
            await db.commit()
            await db.refresh(credential)
            return credential

    @staticmethod
    async def delete(purpose: str) -> bool:
        async with async_session_factory() as db:
            credential = await db.get(Credential, purpose)
            if credential is None:
                return False
            await db.delete(credential)
            await db.commit()
            return True

    @staticmethod
    async def exists(purpose: str) -> bool:
        async with async_session_factory() as db:
            return bool(await db.get(Credential, purpose))

    @staticmethod
    async def list_all() -> list[Credential]:
        async with async_session_factory() as db:
            result = await db.execute(select(Credential).order_by(Credential.purpose))
            return list(result.scalars().all())
