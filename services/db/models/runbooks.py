import uuid
from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.db.models.base import Base, TimestampMixin


class Runbook(Base, TimestampMixin):
    __tablename__ = "runbooks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    service: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    triggers: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    raw_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    sections: Mapped[list["RunbookSection"]] = relationship(
        back_populates="runbook",
        cascade="all, delete-orphan",
        order_by="RunbookSection.order_index.asc()",
        lazy="selectin",
    )
