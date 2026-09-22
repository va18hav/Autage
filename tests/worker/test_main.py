import json
from uuid import uuid4
import pytest
import services.worker.main as worker_mod
from services.agent.llm import LlmResolver
from services.db.models.incident import Incident, IncidentStatus
from services.worker.main import run_agent_task
from tests.conftest import InMemoryAsyncSession

class _FakeRedisPublisher:
    def __init__(self):
        self.published: list[tuple[str, dict]] = []

    async def publish(self, channel: str, message: str):
        self.published.append((channel, json.loads(message)))


class _FakeGraph:
    def __init__(self, chunks=None, exc: Exception | None = None):
        self._chunks = chunks or []
        self._exc = exc

    async def astream(self, _initial_state, stream_mode="updates"):
        if self._exc is not None:
            raise self._exc
        for chunk in self._chunks:
            yield chunk


@pytest.mark.anyio
async def test_worker_run_agent_task_completes_and_publishes_events(monkeypatch):
    session = InMemoryAsyncSession()
    monkeypatch.setattr(worker_mod, "async_session_factory", session.factory)

    async def _fake_load():
        return LlmResolver(steps={}, credentials={})

    monkeypatch.setattr(LlmResolver, "load", _fake_load)

    inc = Incident(
        id=uuid4(),
        title="Pending triage",
        status=IncidentStatus.PENDING,
        raw_alert={"source": "datadog"},
        fingerprint="fp1",
    )
    session.add(inc)

    fake_graph = _FakeGraph(
        chunks=[
            {"process_alert": {"incident_title": "OOMKill on auth-service", "severity": "P1"}},
            {"recommended_steps": {"recommended_steps": ["Step 1: Rollback", "Step 2: Verify"]}},
        ]
    )
    monkeypatch.setattr(worker_mod, "agent_graph", fake_graph)

    redis_pub = _FakeRedisPublisher()
    ctx = {"redis": redis_pub}

    await run_agent_task(ctx, str(inc.id))

    assert inc.status == IncidentStatus.COMPLETED
    assert inc.title == "OOMKill on auth-service"
    assert inc.recommended_steps == ["Step 1: Rollback", "Step 2: Verify"]

    event_types = [msg["type"] for _, msg in redis_pub.published]
    assert event_types == ["status", "step_complete", "step_complete", "incident_complete"]
