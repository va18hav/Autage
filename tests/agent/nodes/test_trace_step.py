from uuid import uuid4

import pytest

import services.agent.nodes.trace_step as trace_step_mod
from services.agent.nodes.trace_step import traced_step
from services.db.models.incident import StepStatus
from tests.conftest import InMemoryAsyncSession


def test_traced_step_rejects_sync_function():
    with pytest.raises(TypeError, match="requires an async node function"):
        @traced_step("sync_node")
        def sync_fn(state):  # type: ignore[arg-type]
            return state


@pytest.mark.anyio
async def test_traced_step_persists_completed_and_failed_transitions(monkeypatch):
    session = InMemoryAsyncSession()
    monkeypatch.setattr(trace_step_mod, "async_session_factory", session.factory)

    @traced_step("sample_ok_node")
    async def ok_node(state):
        return {"result": "done"}

    inc_id = uuid4()
    out = await ok_node({"incident_id": str(inc_id), "raw_alert": {"a": 1}})
    assert out == {"result": "done"}

    steps = list(session.incident_steps.values())
    assert len(steps) == 1
    assert steps[0].step_name == "sample_ok_node"
    assert steps[0].status == StepStatus.COMPLETED
    assert steps[0].output_data == {"result": "done"}

    @traced_step("sample_failing_node")
    async def bad_node(_state):
        raise RuntimeError("LLM connection reset")

    with pytest.raises(RuntimeError, match="LLM connection reset"):
        await bad_node({"incident_id": str(inc_id)})

    steps = list(session.incident_steps.values())
    assert len(steps) == 2
    failed_step = next(s for s in steps if s.step_name == "sample_failing_node")
    assert failed_step.status == StepStatus.FAILED
    assert "LLM connection reset" in failed_step.error_message
