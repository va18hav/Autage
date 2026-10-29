import json
from uuid import uuid4

import pytest

import services.worker.main as worker_mod
from services.agent.llm import LlmConfigError, LlmResolver
from services.agent.playbooks import IncidentType
from services.db.models.incident import Incident, IncidentStatus
from services.worker.main import WorkerSettings, run_agent_task
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

    diagnosis = {
        "what_happened": "The auth-service container restarted repeatedly.",
        "likely_cause": "The container exceeded its memory limit.",
        "confidence": "high",
        "what_i_found": "The previous container exited with code 137.",
        "missing_information": [],
        "recommended_steps": ["Step 1: Rollback", "Step 2: Verify"],
    }

    fake_graph = _FakeGraph(
        chunks=[
            {
                "triage": {
                    "incident_title": "OOMKill on auth-service",
                    "severity": "P1",
                    "incident_type": IncidentType.CRASH_LOOP,
                }
            },
            {"diagnose": {"diagnosis": diagnosis}},
        ]
    )
    monkeypatch.setattr(worker_mod, "agent_graph", fake_graph)

    redis_pub = _FakeRedisPublisher()
    ctx = {"redis": redis_pub}

    await run_agent_task(ctx, str(inc.id))

    assert inc.status == IncidentStatus.COMPLETED
    assert inc.title == "OOMKill on auth-service"
    assert inc.incident_type == "crash_loop"
    assert inc.analysis == diagnosis
    assert inc.recommended_steps == diagnosis["recommended_steps"]

    event_types = [msg["type"] for _, msg in redis_pub.published]
    assert event_types == ["status", "step_complete", "step_complete", "incident_complete"]

    complete_event = redis_pub.published[-1][1]
    assert complete_event["analysis"] == diagnosis
    assert complete_event["incident_type"] == "crash_loop"
    assert complete_event["recommended_steps"] == diagnosis["recommended_steps"]


@pytest.mark.anyio
async def test_worker_handles_missing_incident_and_config_errors(monkeypatch):
    session = InMemoryAsyncSession()
    monkeypatch.setattr(worker_mod, "async_session_factory", session.factory)

    redis_pub = _FakeRedisPublisher()
    ctx = {"redis": redis_pub}

    # 1. Missing incident returns early without publishing
    await run_agent_task(ctx, str(uuid4()))
    assert redis_pub.published == []

    # 2. LlmConfigError marks incident FAILED and publishes incident_failed
    inc = Incident(
        id=uuid4(),
        title="Pending triage",
        status=IncidentStatus.PENDING,
        raw_alert={"source": "prometheus"},
    )
    session.add(inc)

    async def _fake_load():
        return LlmResolver(steps={}, credentials={})

    monkeypatch.setattr(LlmResolver, "load", _fake_load)
    monkeypatch.setattr(
        worker_mod,
        "agent_graph",
        _FakeGraph(exc=LlmConfigError("Missing OpenAI API key in Integrations.")),
    )

    with pytest.raises(LlmConfigError):
        await run_agent_task(ctx, str(inc.id))

    assert inc.status == IncidentStatus.FAILED
    assert redis_pub.published[-1][1]["type"] == "incident_failed"
    assert "Missing OpenAI API key" in redis_pub.published[-1][1]["error"]
    assert WorkerSettings.max_jobs == 10
    assert run_agent_task in WorkerSettings.functions
