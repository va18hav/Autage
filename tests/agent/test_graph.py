from typing import Any
from uuid import uuid4

import pytest

import services.agent.nodes.collect_evidence as collect_mod
import services.agent.nodes.diagnose as diagnose_mod
import services.agent.nodes.find_runbook as find_runbook_mod
import services.agent.nodes.trace_step as trace_step_mod
import services.agent.nodes.triage as triage_mod
from services.agent.graph import builder
from services.agent.nodes.diagnose import DiagnosisOutput
from services.agent.nodes.triage import AlertTriage
from services.agent.playbooks import IncidentType
from services.agent.state import Confidence, Severity
from services.db.models.incident import StepStatus


class _FakeStructured:
    def __init__(self, response: Any):
        self._response = response

    async def ainvoke(self, _prompt: Any) -> Any:
        return self._response


class _FakeChatModel:
    def __init__(self, structured_response: Any):
        self._response = structured_response

    def with_structured_output(self, _schema: Any) -> _FakeStructured:
        return _FakeStructured(self._response)


def _ok(output: str = "") -> dict[str, Any]:
    return {"ok": True, "output": output, "error": None, "truncated": False}


@pytest.mark.anyio
async def test_fixed_pipeline_collects_evidence_and_persists_diagnosis(
    in_memory_db, monkeypatch
):
    monkeypatch.setattr(trace_step_mod, "async_session_factory", in_memory_db.factory)

    triage = AlertTriage(
        incident_title="Crash loop on auth-service",
        description="auth-service pods are restarting.",
        severity=Severity.P1,
        summary="auth-service is crash-looping in production.",
        incident_type=IncidentType.CRASH_LOOP,
        namespace="production",
        deployment_name="auth-service",
    )
    diagnosis = DiagnosisOutput(
        what_happened="The auth-service container is being OOMKilled and restarted.",
        likely_cause="The container exceeds its memory limit.",
        confidence=Confidence.HIGH,
        what_i_found="The previous container exited with code 137 (OOMKilled).",
        missing_information=[],
        recommended_steps=[
            "Roll back the latest auth-service deployment.",
            "Raise the memory limit after confirming the leak.",
            "Watch restarts for ten minutes.",
        ],
    )

    monkeypatch.setattr(triage_mod, "get_llm", lambda _key: _FakeChatModel(triage))
    monkeypatch.setattr(diagnose_mod, "get_llm", lambda _key: _FakeChatModel(diagnosis))

    async def _fetch_payload(_purpose: str) -> dict[str, Any]:
        return {}

    monkeypatch.setattr(collect_mod.SecretStore, "fetch_payload", _fetch_payload)
    monkeypatch.setattr(collect_mod, "set_cluster_credentials", lambda _payload: None)
    monkeypatch.setattr(collect_mod, "reset_cluster_credentials", lambda _token: None)

    monkeypatch.setattr(
        collect_mod,
        "list_deployment_pods",
        lambda _ns, _name: _ok(
            '{"pods": [{"name": "auth-service-abc", "containers": 1, "ready": 0, "restarts": 7}]}'
        ),
    )
    monkeypatch.setattr(
        collect_mod,
        "get_pod_status",
        lambda _ns, _pod: _ok(
            '{"status": {"containerStatuses": [{"name": "app", "ready": false, '
            '"restartCount": 7, "state": {"waiting": {"reason": "CrashLoopBackOff"}}}]}}'
        ),
    )
    monkeypatch.setattr(
        collect_mod,
        "get_pod_logs_previous",
        lambda _ns, _pod, **_kwargs: _ok("exit code 137: OOMKilled"),
    )
    monkeypatch.setattr(
        collect_mod,
        "get_pod_logs",
        lambda _ns, _pod, **_kwargs: _ok("server starting"),
    )
    monkeypatch.setattr(
        collect_mod,
        "get_deployment",
        lambda _ns, _name: _ok('{"desired": 3, "available": 0}'),
    )
    monkeypatch.setattr(
        collect_mod,
        "get_events",
        lambda _ns: _ok("OOMKilling auth-service-abc"),
    )

    async def _find_runbooks(service: str | None, incident_type: str):
        assert service == "auth-service"
        assert incident_type == "crash_loop"
        return [
            {
                "runbook_id": "runbook-1",
                "title": "Auth OOM runbook",
                "service": "auth-service",
                "description": None,
                "score": 100,
                "sections": [
                    {
                        "order_index": 0,
                        "heading": "Rollback",
                        "content": "Roll back the deployment.",
                        "truncated": False,
                    }
                ],
            }
        ]

    monkeypatch.setattr(find_runbook_mod, "find_runbooks_for_incident", _find_runbooks)

    graph = builder.compile()
    state = await graph.ainvoke(
        {
            "incident_id": str(uuid4()),
            "raw_alert": {"alert": "CrashLoopBackOff", "namespace": "production"},
        }
    )

    assert state["incident_type"] == IncidentType.CRASH_LOOP
    assert state["pod_name"] == "auth-service-abc"
    assert state["container_name"] == "app"
    assert state["diagnosis"]["recommended_steps"][0].startswith("Roll back")
    assert state["diagnosis"]["confidence"] == Confidence.HIGH
    assert "Rollback" in state["runbooks_summary"]

    recorded_steps = [step.step_name for step in in_memory_db.incident_steps.values()]
    assert recorded_steps == ["triage", "collect_evidence", "find_runbook", "diagnose"]
    assert all(
        step.status == StepStatus.COMPLETED
        for step in in_memory_db.incident_steps.values()
    )


@pytest.mark.anyio
async def test_unsupported_incident_skips_playbook_and_diagnosis_model(
    in_memory_db, monkeypatch
):
    monkeypatch.setattr(trace_step_mod, "async_session_factory", in_memory_db.factory)

    triage = AlertTriage(
        incident_title="Disk filling on cache node",
        description="A node is reporting low disk space.",
        severity=Severity.P2,
        summary="The cache node is running out of disk.",
        incident_type=IncidentType.OTHER,
        namespace="production",
    )

    monkeypatch.setattr(triage_mod, "get_llm", lambda _key: _FakeChatModel(triage))

    def _unexpected_llm(_key: Any) -> None:
        raise AssertionError("diagnose must not call the model for unsupported incidents")

    monkeypatch.setattr(diagnose_mod, "get_llm", _unexpected_llm)

    graph = builder.compile()
    state = await graph.ainvoke(
        {
            "incident_id": str(uuid4()),
            "raw_alert": {"alert": "DiskPressure"},
        }
    )

    assert state["evidence"] == []
    assert state["diagnosis"]["confidence"] == Confidence.LOW
    assert "specialised playbook" in state["diagnosis"]["likely_cause"]
    assert len(state["diagnosis"]["recommended_steps"]) >= 3

    recorded_steps = [step.step_name for step in in_memory_db.incident_steps.values()]
    assert recorded_steps == ["triage", "collect_evidence", "find_runbook", "diagnose"]
