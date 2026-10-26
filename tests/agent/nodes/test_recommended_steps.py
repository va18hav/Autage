from uuid import uuid4

import pytest

import services.agent.nodes.recommended_steps as rec_mod
import services.agent.nodes.trace_step as trace_step_mod
from services.agent.nodes.recommended_steps import RecommendedSteps, recommended_steps
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


class _FlakyStructured:
    """First call drifts (drops the required list), later calls comply."""

    def __init__(self, drift, good):
        self._responses = [drift, good]

    async def ainvoke(self, _prompt):
        return self._responses.pop(0) if len(self._responses) > 1 else self._responses[0]


class _FlakyLLM:
    def __init__(self, drift, good):
        self._drift, self._good = drift, good

    def with_structured_output(self, _schema):
        return _FlakyStructured(self._drift, self._good)


@pytest.mark.anyio
async def test_recommended_steps_node(monkeypatch):
    session = InMemoryAsyncSession()
    monkeypatch.setattr(trace_step_mod, "async_session_factory", session.factory)

    expected = RecommendedSteps(
        reasoning="Rollback and increase memory limits",
        recommended_steps=[
            "Run `kubectl rollout undo deployment/auth-service -n production`.",
            "Increase container memory limit from 512Mi to 1Gi.",
        ],
    )
    monkeypatch.setattr(rec_mod, "get_llm", lambda _step: _FakeLLM(expected))

    out = await recommended_steps(
        {
            "incident_id": str(uuid4()),
            "incident_title": "OOMKill on auth-service",
            "severity": "P1",
            "summary": "Pod crashing with exit code 137",
            "logs_summary": "OOMKilled at 512Mi",
            "runbooks_summary": "Rollback deployment/auth-service",
        }
    )

    assert len(out["recommended_steps"]) == 2
    assert "kubectl rollout undo" in out["recommended_steps"][0]


@pytest.mark.anyio
async def test_recommended_steps_node_retries_on_schema_drift(monkeypatch):
    session = InMemoryAsyncSession()
    monkeypatch.setattr(trace_step_mod, "async_session_factory", session.factory)

    drift = RecommendedSteps(reasoning="Forgot the list", recommended_steps=[])
    good = RecommendedSteps(
        reasoning="Rollback and increase memory limits",
        recommended_steps=["Scale down the deployment. "],
    )
    monkeypatch.setattr(rec_mod, "get_llm", lambda _step: _FlakyLLM(drift, good))

    out = await recommended_steps(
        {
            "incident_id": str(uuid4()),
            "incident_title": "OOMKill on auth-service",
            "severity": "P1",
            "summary": "Pod crashing with exit code 137",
            "logs_summary": "OOMKilled at 512Mi",
            "runbooks_summary": "",
        }
    )

    assert out["recommended_steps"] == good.recommended_steps
