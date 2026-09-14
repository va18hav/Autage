from uuid import uuid4

import pytest

import services.agent.nodes.fetch_logs as fetch_logs_mod
import services.agent.nodes.trace_step as trace_step_mod
from services.agent.nodes.fetch_logs import (
    KubectlCommand,
    KubectlPlan,
    KubectlTool,
    fetch_logs,
)
from services.db.models.runbooks import Runbook


class _FakeStructured:
    def __init__(self, resp):
        self._resp = resp

    async def ainvoke(self, _prompt):
        return self._resp


class _FakeLLM:
    def __init__(self, plan, summary_text):
        self._plan = plan
        self._summary_text = summary_text

    def with_structured_output(self, _schema):
        return _FakeStructured(self._plan)

    async def ainvoke(self, _prompt):
        return self._summary_text


@pytest.mark.anyio
async def test_fetch_logs_node_executes_commands_and_summarizes(in_memory_db, monkeypatch):
    monkeypatch.setattr(trace_step_mod, "async_session_factory", in_memory_db.factory)
    monkeypatch.setattr(fetch_logs_mod, "async_session_factory", in_memory_db.factory)

    # Seed one runbook so runbooks_available is True
    in_memory_db.add(
        Runbook(title="OOM Runbook", service="auth", raw_content="# OOM")
    )

    plan = KubectlPlan(
        reasoning="Check crashed pod logs and namespace events",
        runbooks_needed=True,
        commands=[
            KubectlCommand(
                tool=KubectlTool.GET_POD_LOGS_PREVIOUS,
                namespace="production",
                pod_name="auth-service-xyz",
                tail=50,
            ),
            KubectlCommand(
                tool=KubectlTool.GET_EVENTS,
                namespace="production",
            ),
        ],
    )
    fake_llm = _FakeLLM(plan, "Pod auth-service-xyz crashed with OOMKilled (exit code 137).")
    monkeypatch.setattr(fetch_logs_mod, "get_llm", lambda _step: fake_llm)

    out = await fetch_logs(
        {
            "incident_id": str(uuid4()),
            "raw_alert": {"pod_name": "auth-service-xyz"},
            "incident_title": "OOMKill on auth-service",
            "severity": "P1",
            "summary": "Memory usage critical",
        }
    )

    assert out["runbooks_available"] is True
    assert out["runbooks_needed"] is True
    assert "get_pod_logs_previous:auth-service-xyz" in out["logs"]
    assert "get_events:production" in out["logs"]
    assert "OOMKilled" in out["logs_summary"]
