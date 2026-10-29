from datetime import datetime, timezone
from uuid import uuid4

import pytest

from services.db.models.incident import Incident, IncidentStatus, IncidentStep, StepStatus
from services.worker import queue
from tests.conftest import InMemoryAsyncSession


def _incident(session: InMemoryAsyncSession, **overrides) -> Incident:
    values = {
        "id": uuid4(),
        "title": "Pending triage",
        "status": IncidentStatus.PENDING,
        "raw_alert": {"source": "test"},
        "fingerprint": str(uuid4()),
        "attempts": 0,
        "next_attempt_at": datetime.now(timezone.utc),
    }
    values.update(overrides)
    incident = Incident(**values)
    session.add(incident)
    return incident


@pytest.mark.anyio
async def test_claim_marks_an_incident_triaging_and_increments_attempts():
    session = InMemoryAsyncSession()
    incident = _incident(session)

    claimed = await queue.claim_next_incident(session, max_attempts=3)

    assert claimed is incident
    assert incident.status == IncidentStatus.TRIAGING
    assert incident.attempts == 1
    assert incident.locked_at is not None


@pytest.mark.anyio
async def test_release_interrupted_leases_clears_stale_locks():
    session = InMemoryAsyncSession()
    incident = _incident(
        session,
        status=IncidentStatus.TRIAGING,
        attempts=1,
        locked_at=datetime.now(timezone.utc),
    )

    released = await queue.release_interrupted_leases(session)

    assert released == 1
    assert incident.locked_at is None


@pytest.mark.anyio
async def test_fail_exhausted_incidents_marks_them_failed():
    session = InMemoryAsyncSession()
    incident = _incident(session, attempts=3)

    failed = await queue.fail_exhausted_incidents(session, max_attempts=3)

    assert failed == [incident.id]
    assert incident.status == IncidentStatus.FAILED
    assert incident.last_error == "Maximum attempts reached."


@pytest.mark.anyio
async def test_mark_interrupted_steps_marks_running_steps_failed():
    session = InMemoryAsyncSession()
    incident = _incident(session)
    step = IncidentStep(
        id=uuid4(),
        incident_id=incident.id,
        step_name="diagnose",
        status=StepStatus.RUNNING,
    )
    session.add(step)

    await queue.mark_interrupted_steps(session, incident.id)

    assert step.status == StepStatus.FAILED
    assert "interrupted" in step.error_message.lower()
