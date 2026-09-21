from typing import Any
from uuid import uuid4

import pytest

from services.agent.graph import builder, runbooks_router
from services.agent.llm import StepKey
from services.agent.nodes import fetch_logs as fetch_logs_mod
from services.agent.nodes import recommended_steps as rec_steps_mod
from services.agent.nodes import refer_runbooks as refer_rb_mod
from services.agent.nodes import trace_step as trace_step_mod
from services.agent.nodes import triage as triage_mod
from services.agent.nodes.fetch_logs import KubectlCommand, KubectlPlan, KubectlTool
from services.agent.nodes.recommended_steps import RecommendedSteps
from services.agent.nodes.refer_runbooks import SectionRequest, SectionsSelection
from services.agent.nodes.triage import AlertTriage, Severity
from services.db.models.incident import StepStatus
from services.db.models.runbooks import Runbook, RunbookSection
from services.secrets.store import SecretStore
import services.agent.tools.runbooks as rb_tools_mod


class _FakeStructured:
    def __init__(self, response: Any):
        self._response = response

    async def ainvoke(self, _prompt: Any) -> Any:
        return self._response


class _FakeChatModel:
    def __init__(self, structured_response: Any = None, text_response: str = ""):
        self._structured = structured_response
        self._text = text_response

    def with_structured_output(self, _schema: Any) -> _FakeStructured:
        return _FakeStructured(self._structured)

    async def ainvoke(self, _prompt: Any) -> str:
        return self._text


def test_runbooks_router_branching():
    assert runbooks_router({"runbooks_needed": True}) == "refer_runbooks"
    assert runbooks_router({"runbooks_needed": False}) == "recommended_steps"
    assert runbooks_router({}) == "recommended_steps"


@pytest.mark.anyio
async def test_compiled_graph_p1_with_runbooks_and_p3_fast_path(in_memory_db, monkeypatch):
    monkeypatch.setattr(trace_step_mod, "async_session_factory", in_memory_db.factory)
    monkeypatch.setattr(fetch_logs_mod, "async_session_factory", in_memory_db.factory)
    monkeypatch.setattr(rb_tools_mod, "async_session_factory", in_memory_db.factory)

    rb = Runbook(
        title="Auth Service OOMKill Runbook",
        service="auth-service",
        raw_content="# Auth\n## Rollback\nUndo deployment",
    )
    in_memory_db.add(rb)
    in_memory_db.add(
        RunbookSection(
            runbook=rb,
            order_index=0,
            heading="Rollback",
            content="Run kubectl rollout undo deployment/auth-service -n production",
        )
    )

    models_p1 = {
        StepKey.TRIAGE: _FakeChatModel(
            structured_response=AlertTriage(
                incident_title="OOMKill on auth-service",
                description="Container memory exceeded 99%.",
                severity=Severity.P1,
                summary="auth-service is crash-looping.",
            )
        ),
        StepKey.DIAGNOSTICS: _FakeChatModel(
            structured_response=KubectlPlan(
                reasoning="Fetch previous logs",
                runbooks_needed=True,
                commands=[
                    KubectlCommand(
                        tool=KubectlTool.GET_POD_LOGS_PREVIOUS,
                        namespace="production",
                        pod_name="auth-service-xyz",
                        tail=50,
                    )
                ],
            ),
            text_response="Previous container exited with code 137 (OOMKilled).",
        ),
        StepKey.RUNBOOKS: _FakeChatModel(
            structured_response=SectionsSelection(
                reasoning="Load Rollback section",
                sections=[
                    SectionRequest(
                        runbook_title="Auth Service OOMKill Runbook",
                        section_order_index=0,
                    )
                ],
            ),
            text_response="Runbook advises rolling back deployment/auth-service.",
        ),
        StepKey.RECOMMENDATIONS: _FakeChatModel(
            structured_response=RecommendedSteps(
                reasoning="Rollback and bump memory",
                recommended_steps=[
                    "Run `kubectl rollout undo deployment/auth-service -n production`.",
                    "Increase memory limit to 1Gi.",
                ],
            )
        ),
    }

    for mod in (triage_mod, fetch_logs_mod, refer_rb_mod, rec_steps_mod):
        monkeypatch.setattr(mod, "get_llm", lambda step_key: models_p1[step_key])

    graph = builder.compile()
    p1_state = await graph.ainvoke(
        {
            "incident_id": str(uuid4()),
            "raw_alert": {"source": "datadog", "pod_name": "auth-service-xyz"},
        }
    )

    assert p1_state["severity"] == Severity.P1
    assert "OOMKilled" in p1_state["logs_summary"]
    assert "rolling back" in p1_state["runbooks_summary"]
    assert len(p1_state["recommended_steps"]) == 2

    recorded_steps = [s.step_name for s in in_memory_db.incident_steps.values()]
    assert recorded_steps == [
        "triage",
        "route_p1",
        "fetch_logs",
        "refer_runbooks",
        "recommended_steps",
    ]
    assert all(s.status == StepStatus.COMPLETED for s in in_memory_db.incident_steps.values())
