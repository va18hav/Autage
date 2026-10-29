from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.db.models.incident import Incident, IncidentStatus, IncidentStep, StepStatus

MAX_ERROR_LENGTH = 2000


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _error_text(error: str) -> str:
    return error[:MAX_ERROR_LENGTH]


async def release_interrupted_leases(db: AsyncSession) -> int:
    """Release TRIAGING rows held by the previous worker process.

    The worker is single-instance in v1, so every TRIAGING row at startup is
    necessarily stale. With multiple workers this must become a lease check.
    """
    result = await db.execute(
        select(Incident).where(
            Incident.status == IncidentStatus.TRIAGING,
            Incident.locked_at.is_not(None),
        )
    )
    incidents = result.scalars().all()
    for incident in incidents:
        incident.locked_at = None
    await db.commit()
    return len(incidents)


async def fail_exhausted_incidents(
    db: AsyncSession,
    max_attempts: int,
) -> list[UUID]:
    """Mark queued incidents that have used all retry attempts as failed."""
    result = await db.execute(
        select(Incident).where(
            Incident.status.in_([IncidentStatus.PENDING, IncidentStatus.TRIAGING]),
        )
    )
    exhausted: list[UUID] = []
    for incident in result.scalars().all():
        if (incident.attempts or 0) < max_attempts:
            continue
        incident.status = IncidentStatus.FAILED
        incident.locked_at = None
        incident.last_error = incident.last_error or "Maximum attempts reached."
        exhausted.append(incident.id)
    if exhausted:
        await db.commit()
    return exhausted


async def claim_next_incident(
    db: AsyncSession,
    max_attempts: int,
) -> Incident | None:
    """Claim one due incident and hold it for this worker."""
    now = _now()
    result = await db.execute(
        select(Incident)
        .where(
            or_(
                and_(
                    Incident.status == IncidentStatus.PENDING,
                    Incident.next_attempt_at <= now,
                ),
                and_(
                    Incident.status == IncidentStatus.TRIAGING,
                    Incident.locked_at.is_(None),
                ),
            ),
            Incident.attempts < max_attempts,
        )
        .order_by(Incident.next_attempt_at.asc(), Incident.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    incident = result.scalar_one_or_none()
    if incident is None:
        await db.commit()
        return None

    incident.status = IncidentStatus.TRIAGING
    incident.attempts = (incident.attempts or 0) + 1
    incident.locked_at = now
    incident.last_error = None
    await db.commit()
    return incident


async def mark_interrupted_steps(db: AsyncSession, incident_id: UUID) -> None:
    """Mark steps left RUNNING by a killed worker as interrupted."""
    result = await db.execute(
        select(IncidentStep).where(
            IncidentStep.incident_id == incident_id,
            IncidentStep.status == StepStatus.RUNNING,
        )
    )
    changed = False
    for step in result.scalars().all():
        step.status = StepStatus.FAILED
        step.error_message = "Worker interrupted before step completion."
        changed = True
    if changed:
        await db.commit()


async def mark_incident_completed(
    db: AsyncSession,
    incident_id: UUID,
    *,
    title: str,
    incident_type: str | None,
    analysis: dict,
    recommended_steps: list | None,
) -> None:
    incident = await db.get(Incident, incident_id)
    if incident is None:
        return
    incident.title = title
    incident.status = IncidentStatus.COMPLETED
    incident.incident_type = incident_type
    incident.analysis = analysis
    incident.recommended_steps = recommended_steps
    incident.locked_at = None
    incident.last_error = None
    await db.commit()


async def mark_incident_failed(
    db: AsyncSession,
    incident_id: UUID,
    error: str,
) -> None:
    incident = await db.get(Incident, incident_id)
    if incident is None:
        return
    incident.status = IncidentStatus.FAILED
    incident.locked_at = None
    incident.last_error = _error_text(error)
    await db.commit()


async def schedule_incident_retry(
    db: AsyncSession,
    incident_id: UUID,
    error: str,
    delay_seconds: int,
) -> None:
    incident = await db.get(Incident, incident_id)
    if incident is None:
        return
    incident.status = IncidentStatus.PENDING
    incident.locked_at = None
    incident.next_attempt_at = _now() + timedelta(seconds=delay_seconds)
    incident.last_error = _error_text(error)
    await db.commit()
