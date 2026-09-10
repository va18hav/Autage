from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from services.db.models.base import Base, TimestampMixin


class Credential(Base, TimestampMixin):
    """A stored integration credential (API key, base URL, etc.).

    `purpose` identifies what the credential is for and is the natural PK:
    LLM provider ids ("openai", "google", ...) now; other integrations
    ("slack", "pagerduty", ...) later.

    The secret payload is always Fernet-encrypted — see services.secrets.crypto.
    Only a masked preview is ever exposed outside this table.
    """

    __tablename__ = "credentials"

    purpose: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
    )

    encrypted_payload: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Masked, human-readable fingerprint (e.g. "sk-…a1b2") shown in the UI
    preview: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
