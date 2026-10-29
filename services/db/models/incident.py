import enum
import uuid
from datetime import datetime
from typing import Any
from sqlalchemy import (
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from services.db.models.base import Base, TimestampMixin

class IncidentStatus(str, enum.Enum):
    PENDING = "PENDING"
    TRIAGING = "TRIAGING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class Incident(Base, TimestampMixin):
    __tablename__ = "incidents"
    __table_args__ = (
        Index(
            "ix_incidents_pending_queue",
            "next_attempt_at",
            "created_at",
            postgresql_where=text("status = 'PENDING'"),
        ),
        Index(
            "ix_incidents_triaging_queue",
            "locked_at",
            "created_at",
            postgresql_where=text("status = 'TRIAGING'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    status: Mapped[IncidentStatus] = mapped_column(
        SQLEnum(IncidentStatus),
        default=IncidentStatus.PENDING,
        nullable=False
    )

    raw_alert: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False
    )

    fingerprint: Mapped[str | None] = mapped_column(
        String(128),
        index=True,
        nullable=True
    )

    incident_type: Mapped[str | None] = mapped_column(
        String(32),
        index=True,
        nullable=True
    )

    analysis: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True
    )

    recommended_steps: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable= True
    )

    # Postgres-backed work queue fields. PENDING incidents are claimable when
    # next_attempt_at is due; TRIAGING incidents are resumable after a restart.
    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    steps: Mapped[list["IncidentStep"]] = relationship(
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="IncidentStep.created_at.asc()",
        lazy="selectin"
    )


class StepStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class IncidentStep(Base, TimestampMixin):
    __tablename__ = "incident_steps"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "incidents.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )

    step_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    status: Mapped[StepStatus] = mapped_column(
        SQLEnum(StepStatus),
        default=StepStatus.RUNNING,
        nullable=False
    )

    input_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True
    )

    output_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    incident: Mapped["Incident"] = relationship(back_populates="steps")


