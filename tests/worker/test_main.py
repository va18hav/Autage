import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest

import services.worker.main as worker_mod
from services.agent.llm import LlmConfigError, LlmResolver
from services.agent.playbooks import IncidentType
from services.db.models.incident import Incident, IncidentStatus
from services.worker.main import run_agent_task
from tests.conftest import FakeRedis, InMemoryAsyncSession


class _FakeSnapshot:
    def __init__(
        self,
        values: dict | None = None,
        next_nodes: tuple[str, ...] = (),
        created_at: datetime | None = None,
    ):
        self.values = values or {}
        self.next = next_nodes
        self.created_at = created_at


class _FakeGraph:
    def __init__(
        self,
        snapshots: list[_FakeSnapshot],
        chunks: list[dict] | None = None,
        exc: Exception | None = None,
    ):
        self._snapshots = list(snapshots)
        self._chunks = chunks or []
        self._exc = exc
        self.stream_inputs: list[object] = []

    async def aget_state(self, _config):
        if self._snapshots:
            return self._snapshots.pop(0)
        return _FakeSnapshot()

    async def astream(
        self,
        stream_input,
        config=None,
        stream_mode=None,
        durability=None,
    ):
        self.stream_inputs.append(stream_input)
        if self._exc is not None:
            raise self._exc
        for chunk in self._chunks:
            yield chunk


def _diagnosis() -> dict:
    return {
        "what_happened": "The auth-service container restarted repeatedly.",
        "likely_cause": "The container exceeded its memory limit.",
        "confidence": "high",
        "what_i_found": "The previous container exited with code 137.",
        "missing_information": [],
        "recommended_steps": ["Step 1: Rollback", "Step 2: Verify"],
    }


def _full_values() -> dict:
    return {
        "incident_title": "OOMKill on auth-service",
        "incident_type": IncidentType.CRASH_LOOP,
        "diagnosis": _diagnosis(),
    }


def _triage_incident(
    session: InMemoryAsyncSession,
    *,
    attempts: int = 1,
    status: IncidentStatus = IncidentStatus.TRIAGING,
) -> Incident:
    incident = Incident(
        id=uuid4(),
        title="Pending triage",
        status=status,
        raw_alert={"source": "datadog"},
        fingerprint="fp1",
        attempts=attempts,
        next_attempt_at=datetime.now(timezone.utc),
        locked_at=datetime.now(timezone.utc),
    )
    session.add(incident)
    return incident


@pytest.fixture
def resolver(monkeypatch):
    async def _fake_load():
        return LlmResolver(steps={}, credentials={})

    monkeypatch.setattr(LlmResolver, "load", _fake_load)


@pytest.mark.anyio
async def test_worker_completes_a_fresh_incident(monkeypatch, resolver):
    session = InMemoryAsyncSession()
    monkeypatch.setattr(worker_mod, "async_session_factory", session.factory)
    incident = _triage_incident(session)

    graph = _FakeGraph(
        snapshots=[
            _FakeSnapshot(),
            _FakeSnapshot(values=_full_values(), created_at=datetime.now(timezone.utc)),
        ],
        chunks=[
            {"triage": {"incident_title": "OOMKill on auth-service"}},
            {"diagnose": {"diagnosis": _diagnosis()}},
        ],
    )
    redis_client = FakeRedis()

    await run_agent_task(redis_client, graph, str(incident.id))

    assert incident.status == IncidentStatus.COMPLETED
    assert incident.title == "OOMKill on auth-service"
    assert incident.incident_type == "crash_loop"
    assert incident.analysis == _diagnosis()
    assert incident.recommended_steps == _diagnosis()["recommended_steps"]
    assert incident.locked_at is None
    assert graph.stream_inputs[0]["incident_id"] == str(incident.id)

    published = [json.loads(payload) for _, payload in redis_client.published]
    assert [item["type"] for item in published] == [
        "status",
        "step_complete",
        "step_complete",
        "incident_complete",
    ]


@pytest.mark.anyio
async def test_worker_resumes_from_checkpoint_without_replaying_triage(
    monkeypatch,
    resolver,
):
    session = InMemoryAsyncSession()
    monkeypatch.setattr(worker_mod, "async_session_factory", session.factory)
    incident = _triage_incident(session)

    graph = _FakeGraph(
        snapshots=[
            _FakeSnapshot(
                values={"incident_title": "OOMKill on auth-service"},
                next_nodes=("diagnose",),
                created_at=datetime.now(timezone.utc),
            ),
            _FakeSnapshot(values=_full_values(), created_at=datetime.now(timezone.utc)),
        ],
        chunks=[{"diagnose": {"diagnosis": _diagnosis()}}],
    )
    redis_client = FakeRedis()

    await run_agent_task(redis_client, graph, str(incident.id))

    assert graph.stream_inputs == [None]
    assert incident.status == IncidentStatus.COMPLETED


@pytest.mark.anyio
async def test_worker_finalizes_a_completed_checkpoint_without_calling_the_graph(
    monkeypatch,
    resolver,
):
    session = InMemoryAsyncSession()
    monkeypatch.setattr(worker_mod, "async_session_factory", session.factory)
    incident = _triage_incident(session)

    values = _full_values()
    graph = _FakeGraph(
        snapshots=[
            _FakeSnapshot(
                values=values,
                next_nodes=(),
                created_at=datetime.now(timezone.utc),
            )
        ],
    )

    await run_agent_task(FakeRedis(), graph, str(incident.id))

    assert graph.stream_inputs == []
    assert incident.status == IncidentStatus.COMPLETED
    assert incident.analysis == _diagnosis()


@pytest.mark.anyio
async def test_worker_schedules_retry_for_a_retryable_error(monkeypatch, resolver):
    session = InMemoryAsyncSession()
    monkeypatch.setattr(worker_mod, "async_session_factory", session.factory)
    incident = _triage_incident(session, attempts=1)

    graph = _FakeGraph(
        snapshots=[_FakeSnapshot()],
        exc=RuntimeError("temporary failure"),
    )
    redis_client = FakeRedis()

    await run_agent_task(redis_client, graph, str(incident.id))

    assert incident.status == IncidentStatus.PENDING
    assert incident.locked_at is None
    assert "temporary failure" in incident.last_error
    assert incident.next_attempt_at > datetime.now(timezone.utc)
    published = [json.loads(payload) for _, payload in redis_client.published]
    assert published[-1]["type"] == "status"
    assert published[-1]["status"] == "PENDING"


@pytest.mark.anyio
async def test_worker_fails_an_incident_after_max_attempts(monkeypatch, resolver):
    session = InMemoryAsyncSession()
    monkeypatch.setattr(worker_mod, "async_session_factory", session.factory)
    incident = _triage_incident(session, attempts=3)

    graph = _FakeGraph(
        snapshots=[_FakeSnapshot()],
        exc=RuntimeError("still failing"),
    )
    redis_client = FakeRedis()

    await run_agent_task(redis_client, graph, str(incident.id))

    assert incident.status == IncidentStatus.FAILED
    assert incident.locked_at is None
    assert "still failing" in incident.last_error
    published = [json.loads(payload) for _, payload in redis_client.published]
    assert published[-1]["type"] == "incident_failed"


@pytest.mark.anyio
async def test_worker_marks_config_errors_terminal(monkeypatch, resolver):
    session = InMemoryAsyncSession()
    monkeypatch.setattr(worker_mod, "async_session_factory", session.factory)
    incident = _triage_incident(session, attempts=1)

    graph = _FakeGraph(
        snapshots=[_FakeSnapshot()],
        exc=LlmConfigError("Missing OpenAI API key in Integrations."),
    )
    redis_client = FakeRedis()

    await run_agent_task(redis_client, graph, str(incident.id))

    assert incident.status == IncidentStatus.FAILED
    assert "Missing OpenAI API key" in incident.last_error
    published = [json.loads(payload) for _, payload in redis_client.published]
    assert published[-1]["type"] == "incident_failed"


@pytest.mark.anyio
async def test_worker_ignores_a_missing_incident(monkeypatch):
    session = InMemoryAsyncSession()
    monkeypatch.setattr(worker_mod, "async_session_factory", session.factory)
    redis_client = FakeRedis()

    await run_agent_task(redis_client, _FakeGraph([]), str(uuid4()))

    assert redis_client.published == []
