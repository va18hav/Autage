import enum
import uuid
from typing import Any
from sqlalchemy import Enum as SQLEnum, ForeignKey, String, Text
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

    recommended_steps: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable= True
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


