from sqlalchemy import Float, ForeignKey, Integer, String, Text
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


class LlmStepConfig(Base, TimestampMixin):
    """Per-step LLM model selection for the agent pipeline.

    One row per pipeline step (triage / diagnostics / runbooks /
    recommendations). Missing rows mean "use the built-in default" — that
    fallback lives in services.agent.llm.resolver, not here.
    """

    __tablename__ = "llm_step_configs"

    step_key: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
    )

    provider_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    model_id: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    temperature: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    max_output_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # Reserved: typed now so step-level credential selection (e.g. two keys
    # for the same provider later) is additive rather than a migration pain.
    credential_purpose: Mapped[str | None] = mapped_column(
        String(50),
        ForeignKey("credentials.purpose", ondelete="SET NULL"),
        nullable=True,
    )
