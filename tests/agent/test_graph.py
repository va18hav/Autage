from typing import Any
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage

import services.agent.nodes.diagnose as diagnose_mod
import services.agent.nodes.investigate as investigate_mod
import services.agent.nodes.search_runbook as search_runbook_mod
import services.agent.nodes.trace_step as trace_step_mod
import services.agent.nodes.triage as triage_mod
from services.agent.graph import builder
from services.agent.incidents import IncidentType
from services.agent.nodes.diagnose import DiagnosisOutput
from services.agent.nodes.triage import AlertTriage
from services.agent.state import Confidence, Severity
from services.db.models.incident import StepStatus


def test_pipeline_graph_is_wired_in_fixed_order():
    graph = builder.compile().get_graph()

    assert {
        "__start__",
        "triage",
        "search_runbook",
        "investigate",
        "diagnose",
        "__end__",
    } == set(graph.nodes)
    assert {
        ("__start__", "triage"),
        ("triage", "search_runbook"),
        ("search_runbook", "investigate"),
        ("investigate", "diagnose"),
        ("diagnose", "__end__"),
    } == {(edge.source, edge.target) for edge in graph.edges}


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


class _FakeToolCallingModel:
    def __init__(self, responses: list[AIMessage]):
        self._responses = list(responses)
        self.messages: list[list] = []

    def bind_tools(self, _tools: Any) -> "_FakeToolCallingModel":
        return self

    async def ainvoke(self, messages: Any) -> AIMessage:
        self.messages.append(list(messages))
        return self._responses.pop(0)


def _calls(*items: tuple[str, dict, str]) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {"name": name, "args": args, "id": call_id, "type": "tool_call"}
            for name, args, call_id in items
        ],
    )


def _ok(output: str = "") -> dict[str, Any]:
    return {"ok": True, "output": output, "error": None, "truncated": False}


@pytest.mark.anyio
async def test_pipeline_collects_evidence_and_persists_diagnosis(
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

    investigate_model = _FakeToolCallingModel(
        [
            _calls(
                (
                    "list_deployment_pods",
                    {"namespace": "production", "deployment_name": "auth-service"},
                    "call-1",
                )
            ),
            _calls(
                (
                    "get_pod_status",
                    {"namespace": "production", "pod_name": "auth-service-abc"},
                    "call-2",
                )
            ),
            _calls(
                (
                    "get_pod_logs_previous",
                    {"namespace": "production", "pod_name": "auth-service-abc"},
                    "call-3",
                ),
                (
                    "get_pod_logs",
                    {"namespace": "production", "pod_name": "auth-service-abc"},
                    "call-4",
                ),
                (
                    "get_deployment",
                    {"namespace": "production", "deployment_name": "auth-service"},
                    "call-5",
                ),
                ("get_events", {"namespace": "production"}, "call-6"),
            ),
            AIMessage(content="Investigation complete."),
        ]
    )

    monkeypatch.setattr(triage_mod, "get_llm", lambda _key: _FakeChatModel(triage))
    monkeypatch.setattr(
        investigate_mod, "get_llm", lambda _key: investigate_model
    )
    monkeypatch.setattr(diagnose_mod, "get_llm", lambda _key: _FakeChatModel(diagnosis))

    async def _fetch_payload(_purpose: str) -> dict[str, Any]:
        return {"server_url": "https://k8s.internal:6443", "token": "token"}

    monkeypatch.setattr(investigate_mod.SecretStore, "fetch_payload", _fetch_payload)
    monkeypatch.setattr(
        investigate_mod, "set_cluster_credentials", lambda _payload: None
    )
    monkeypatch.setattr(
        investigate_mod, "reset_cluster_credentials", lambda _token: None
    )

    monkeypatch.setattr(
        investigate_mod,
        "list_deployment_pods",
        lambda _ns, _name: _ok(
            '{"pods": [{"name": "auth-service-abc", "containers": 1, '
            '"ready": 0, "restarts": 7}]}'
        ),
    )
    monkeypatch.setattr(
        investigate_mod,
        "get_pod_status",
        lambda _ns, _pod: _ok(
            '{"status": {"containerStatuses": [{"name": "app", "ready": false, '
            '"restartCount": 7, '
            '"state": {"waiting": {"reason": "CrashLoopBackOff"}}}]}}'
        ),
    )
    monkeypatch.setattr(
        investigate_mod,
        "get_pod_logs_previous",
        lambda _ns, _pod, **_kwargs: _ok("exit code 137: OOMKilled"),
    )
    monkeypatch.setattr(
        investigate_mod,
        "get_pod_logs",
        lambda _ns, _pod, **_kwargs: _ok("server starting"),
    )
    monkeypatch.setattr(
        investigate_mod,
        "get_deployment",
        lambda _ns, _name: _ok('{"desired": 3, "available": 0}'),
    )
    monkeypatch.setattr(
        investigate_mod,
        "get_events",
        lambda _ns: _ok("OOMKilling auth-service-abc"),
    )

    runbook_model = _FakeToolCallingModel(
        [
            _calls(
                (
                    "read_runbook_sections",
                    {"runbook_id": "runbook-1", "section_indexes": [0]},
                    "runbook-call-1",
                )
            ),
            AIMessage(content="Selected the rollback section."),
        ]
    )

    async def _load_runbook_catalog(**_kwargs):
        return [
            {
                "runbook_id": "runbook-1",
                "title": "Auth OOM runbook",
                "service": "auth-service",
                "description": None,
                "score": 100,
                "sections": [{"index": 0, "heading": "Rollback"}],
            }
        ]

    async def _fetch_runbook_sections(
        runbook_id: str,
        section_indexes: list[int],
        *,
        max_total_chars: int,
    ):
        assert runbook_id == "runbook-1"
        assert section_indexes == [0]
        return {
            "ok": True,
            "output": "## Runbook: Auth OOM runbook\n...",
            "error": None,
            "truncated": False,
            "runbook_id": runbook_id,
            "title": "Auth OOM runbook",
            "service": "auth-service",
            "sections": [
                {
                    "index": 0,
                    "heading": "Rollback",
                    "content": "Roll back the deployment.",
                    "truncated": False,
                }
            ],
        }

    monkeypatch.setattr(
        search_runbook_mod, "get_llm", lambda _key: runbook_model
    )
    monkeypatch.setattr(
        search_runbook_mod, "load_runbook_catalog", _load_runbook_catalog
    )
    monkeypatch.setattr(
        search_runbook_mod,
        "fetch_runbook_sections",
        _fetch_runbook_sections,
    )

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
    assert "Roll back the deployment." in state["runbooks_summary"]

    runbook_prompt = runbook_model.messages[0][1].content
    assert "Auth OOM runbook" in runbook_prompt
    assert "0. Rollback" in runbook_prompt
    assert "Roll back the deployment." not in runbook_prompt

    investigation_prompt = investigate_model.messages[0][1].content
    assert "Auth OOM runbook" in investigation_prompt
    assert "Roll back the deployment." in investigation_prompt

    recorded_steps = [step.step_name for step in in_memory_db.incident_steps.values()]
    assert recorded_steps == [
        "triage",
        "search_runbook",
        "investigate",
        "diagnose",
    ]
    assert all(
        step.status == StepStatus.COMPLETED
        for step in in_memory_db.incident_steps.values()
    )


@pytest.mark.anyio
async def test_other_incident_still_collects_evidence_and_diagnoses(
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
    diagnosis = DiagnosisOutput(
        what_happened="A cache node is reporting low disk space.",
        likely_cause="Unclear. Only namespace events were available.",
        confidence=Confidence.LOW,
        what_i_found="A DiskPressure warning was reported in production.",
        missing_information=["No pod or deployment was identified."],
        recommended_steps=[
            "Identify the affected node and its workloads.",
            "Inspect disk usage on the node.",
            "Clear or expand disk space and verify recovery.",
        ],
    )

    investigate_model = _FakeToolCallingModel(
        [
            _calls(("get_events", {"namespace": "production"}, "call-1")),
            AIMessage(content="I only have namespace-level evidence."),
        ]
    )

    monkeypatch.setattr(triage_mod, "get_llm", lambda _key: _FakeChatModel(triage))
    monkeypatch.setattr(
        investigate_mod, "get_llm", lambda _key: investigate_model
    )
    monkeypatch.setattr(diagnose_mod, "get_llm", lambda _key: _FakeChatModel(diagnosis))

    async def _fetch_payload(_purpose: str) -> dict[str, Any]:
        return {"server_url": "https://k8s.internal:6443", "token": "token"}

    monkeypatch.setattr(investigate_mod.SecretStore, "fetch_payload", _fetch_payload)
    monkeypatch.setattr(
        investigate_mod, "set_cluster_credentials", lambda _payload: None
    )
    monkeypatch.setattr(
        investigate_mod, "reset_cluster_credentials", lambda _token: None
    )
    monkeypatch.setattr(
        investigate_mod,
        "get_events",
        lambda _ns: _ok("DiskPressure on cache-node-1"),
    )

    async def _no_runbooks(**_kwargs):
        return []

    monkeypatch.setattr(
        search_runbook_mod, "load_runbook_catalog", _no_runbooks
    )

    graph = builder.compile()
    state = await graph.ainvoke(
        {
            "incident_id": str(uuid4()),
            "raw_alert": {"alert": "DiskPressure"},
        }
    )

    assert [item["tool"] for item in state["evidence"]] == ["get_events"]
    assert state["diagnosis"]["confidence"] == Confidence.LOW
    assert state["diagnosis"]["likely_cause"].startswith("Unclear")
    assert len(state["diagnosis"]["recommended_steps"]) >= 3

    recorded_steps = [step.step_name for step in in_memory_db.incident_steps.values()]
    assert recorded_steps == [
        "triage",
        "search_runbook",
        "investigate",
        "diagnose",
    ]
    assert all(
        step.status == StepStatus.COMPLETED
        for step in in_memory_db.incident_steps.values()
    )
