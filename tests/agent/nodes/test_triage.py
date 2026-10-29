from uuid import uuid4

import pytest

import services.agent.nodes.trace_step as trace_step_mod
import services.agent.nodes.triage as triage_mod
from services.agent.nodes.triage import AlertTriage, Severity, process_alert
from services.agent.playbooks import IncidentType
from tests.conftest import InMemoryAsyncSession


class _FakeStructured:
    def __init__(self, resp):
        self._resp = resp

    async def ainvoke(self, _prompt):
        return self._resp


class _FakeLLM:
    def __init__(self, resp):
        self._resp = resp

    def with_structured_output(self, _schema):
        return _FakeStructured(self._resp)


@pytest.mark.anyio
async def test_process_alert_node(monkeypatch):
    session = InMemoryAsyncSession()
    monkeypatch.setattr(trace_step_mod, "async_session_factory", session.factory)

    expected = AlertTriage(
        incident_title="Auth Service Memory Exhaustion",
        description="Pod memory exceeded 99% and crashed with OOMKilled.",
        severity=Severity.P1,
        summary="Production auth-service is crash-looping due to OOM.",
        incident_type=IncidentType.CRASH_LOOP,
        namespace="production",
        deployment_name="auth-service",
    )
    monkeypatch.setattr(triage_mod, "get_llm", lambda _step: _FakeLLM(expected))

    result = await process_alert(
        {
            "incident_id": str(uuid4()),
            "raw_alert": {"source": "datadog", "pod_name": "auth-service-xyz"},
        }
    )

    assert result["incident_title"] == "Auth Service Memory Exhaustion"
    assert result["severity"] == Severity.P1
    assert result["incident_type"] == IncidentType.CRASH_LOOP
    assert result["deployment_name"] == "auth-service"
    assert "OOM" in result["summary"]
