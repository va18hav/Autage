import uuid
from typing import Any
from sqlalchemy import ForeignKey, Integer, String, Text
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


class RunbookSection(Base, TimestampMixin):
    __tablename__ = "runbook_sections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    runbook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("runbooks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    order_index: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    heading: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    runbook: Mapped["Runbook"] = relationship(
        back_populates="sections",
    )


# Aliases so both singular and plural forms work seamlessly
Runbooks = Runbook
RunbookSections = RunbookSection