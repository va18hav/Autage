import json
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage

import services.agent.nodes.investigate as investigate_mod
import services.agent.nodes.trace_step as trace_step_mod
from services.agent.incidents import IncidentType
from tests.conftest import InMemoryAsyncSession

_RUNBOOK_SUMMARY = (
    "## Runbook: Auth OOM runbook (service: auth-service)\n"
    "### Rollback\nRoll back the deployment."
)


def _ok(output: str = "") -> dict:
    return {"ok": True, "output": output, "error": None, "truncated": False}


def _fail(error: str) -> dict:
    return {"ok": False, "output": "", "error": error, "truncated": False}


def _call(name: str, args: dict, call_id: str) -> AIMessage:
    return _calls((name, args, call_id))


def _calls(*items: tuple[str, dict, str]) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {"name": name, "args": args, "id": call_id, "type": "tool_call"}
            for name, args, call_id in items
        ],
    )


class _FakeToolCallingModel:
    def __init__(self, responses):
        self._responses = list(responses)
        self.tool_names: list[str] = []
        self.messages: list[list] = []

    def bind_tools(self, tools):
        self.tool_names = [item.name for item in tools]
        return self

    async def ainvoke(self, messages):
        self.messages.append(list(messages))
        return self._responses.pop(0)


def _state(**overrides):
    state = {
        "incident_id": str(uuid4()),
        "raw_alert": {},
        "incident_title": "Crash loop on auth-service",
        "summary": "auth-service is crash-looping.",
        "description": "auth-service pods are restarting.",
        "severity": "P1",
        "incident_type": IncidentType.CRASH_LOOP,
        "namespace": "production",
        "pod_name": None,
        "deployment_name": "auth-service",
        "container_name": None,
        "runbooks_summary": _RUNBOOK_SUMMARY,
    }
    state.update(overrides)
    return state


async def _credentials(_purpose):
    return {
        "server_url": "https://k8s.internal:6443",
        "token": "token",
        "ca_cert": "ca",
    }


def _patch_common(monkeypatch):
    session = InMemoryAsyncSession()
    monkeypatch.setattr(trace_step_mod, "async_session_factory", session.factory)
    monkeypatch.setattr(investigate_mod.SecretStore, "fetch_payload", _credentials)
    monkeypatch.setattr(
        investigate_mod, "set_cluster_credentials", lambda _payload: None
    )
    monkeypatch.setattr(
        investigate_mod, "reset_cluster_credentials", lambda _token: None
    )


@pytest.mark.anyio
async def test_model_chooses_tools_and_node_discovers_pod_and_container(monkeypatch):
    _patch_common(monkeypatch)

    monkeypatch.setattr(
        investigate_mod,
        "list_deployment_pods",
        lambda _ns, _name: _ok(
            json.dumps(
                {"pods": [{"name": "auth-abc", "ready": 0, "restarts": 7}]}
            )
        ),
    )
    monkeypatch.setattr(
        investigate_mod,
        "get_pod_status",
        lambda _ns, _pod: _ok(
            json.dumps(
                {
                    "status": {
                        "containerStatuses": [
                            {"name": "app", "ready": False, "restartCount": 7}
                        ]
                    }
                }
            )
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
        lambda _ns: _ok("OOMKilling auth-abc"),
    )

    model = _FakeToolCallingModel(
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
                    {"namespace": "production", "pod_name": "auth-abc"},
                    "call-2",
                )
            ),
            _calls(
                (
                    "get_pod_logs_previous",
                    {"namespace": "production", "pod_name": "auth-abc"},
                    "call-3",
                ),
                (
                    "get_pod_logs",
                    {"namespace": "production", "pod_name": "auth-abc"},
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
    monkeypatch.setattr(investigate_mod, "get_llm", lambda _key: model)

    result = await investigate_mod.investigate(_state())

    assert set(model.tool_names) == {
        "get_pod_status",
        "get_pod_logs",
        "get_pod_logs_previous",
        "get_deployment",
        "list_deployment_pods",
        "get_deployment_history",
        "get_events",
        "search_runbooks",
        "read_runbook_sections",
    }
    assert [item["tool"] for item in result["evidence"]] == [
        "list_deployment_pods",
        "get_pod_status",
        "get_pod_logs_previous",
        "get_pod_logs",
        "get_deployment",
        "get_events",
    ]
    assert result["pod_name"] == "auth-abc"
    assert result["container_name"] == "app"
    assert result["missing_evidence"] == []
    assert result["evidence"][2]["target"] == "production/auth-abc"
    assert result["runbooks_summary"] == _RUNBOOK_SUMMARY

    prompt = model.messages[0][1].content
    assert "Auth OOM runbook" in prompt
    assert "database connection pool" not in prompt


@pytest.mark.anyio
async def test_runbook_tools_add_index_then_fetch_sections(monkeypatch):
    _patch_common(monkeypatch)

    searches = []
    fetches = []

    async def _catalog(service, incident_type, *, query=None):
        searches.append((service, incident_type, query))
        return [
            {
                "runbook_id": "runbook-2",
                "title": "Database pool runbook",
                "service": "auth-service",
                "description": None,
                "score": 90,
                "sections": [
                    {"index": 0, "heading": "Pool exhaustion"},
                ],
            }
        ]

    async def _fetch(
        runbook_id,
        section_indexes,
        *,
        max_total_chars=14_000,
    ):
        fetches.append((runbook_id, section_indexes, max_total_chars))
        return {
            "ok": True,
            "output": (
                "## Runbook: Database pool runbook (service: auth-service)\n"
                "### Pool exhaustion\n"
                "Check the database connection pool."
            ),
            "error": None,
            "truncated": False,
            "runbook_id": runbook_id,
            "title": "Database pool runbook",
            "service": "auth-service",
            "sections": [
                {
                    "index": 0,
                    "heading": "Pool exhaustion",
                    "content": "Check the database connection pool.",
                    "truncated": False,
                }
            ],
        }

    monkeypatch.setattr(investigate_mod, "load_runbook_catalog", _catalog)
    monkeypatch.setattr(investigate_mod, "fetch_runbook_sections", _fetch)
    monkeypatch.setattr(
        investigate_mod, "get_events", lambda _ns: _ok("OOMKilling auth-abc")
    )

    model = _FakeToolCallingModel(
        [
            _call("get_events", {"namespace": "production"}, "call-1"),
            _call(
                "search_runbooks",
                {"query": "database connection pool"},
                "call-2",
            ),
            _call(
                "read_runbook_sections",
                {"runbook_id": "runbook-2", "section_indexes": [0]},
                "call-3",
            ),
            AIMessage(content="I have enough evidence."),
        ]
    )
    monkeypatch.setattr(investigate_mod, "get_llm", lambda _key: model)

    result = await investigate_mod.investigate(_state())

    assert searches == [
        ("auth-service", "crash_loop", "database connection pool")
    ]
    assert fetches == [("runbook-2", [0], 14_000)]
    assert [item["tool"] for item in result["evidence"]] == ["get_events"]
    assert result["missing_evidence"] == []
    assert "Auth OOM runbook" in result["runbooks_summary"]
    assert "Database pool runbook" in result["runbooks_summary"]
    assert "Check the database connection pool." in result["runbooks_summary"]


@pytest.mark.anyio
async def test_failed_tool_call_is_evidence_and_missing_information(monkeypatch):
    _patch_common(monkeypatch)

    monkeypatch.setattr(
        investigate_mod,
        "get_pod_status",
        lambda _ns, _pod: _fail("pod status unavailable"),
    )

    model = _FakeToolCallingModel(
        [
            _call(
                "get_pod_status",
                {"namespace": "production", "pod_name": "auth-abc"},
                "call-1",
            ),
            AIMessage(content="I could not read the pod."),
        ]
    )
    monkeypatch.setattr(investigate_mod, "get_llm", lambda _key: model)

    result = await investigate_mod.investigate(_state(pod_name="auth-abc"))

    assert len(result["evidence"]) == 1
    assert result["evidence"][0]["ok"] is False
    assert any(
        "get_pod_status failed" in item for item in result["missing_evidence"]
    )


@pytest.mark.anyio
async def test_missing_namespace_returns_before_calling_the_model(monkeypatch):
    _patch_common(monkeypatch)

    def _forbidden(_key):
        raise AssertionError("The model must not run without a namespace")

    monkeypatch.setattr(investigate_mod, "get_llm", _forbidden)

    result = await investigate_mod.investigate(_state(namespace=None))

    assert result["evidence"] == []
    assert len(result["missing_evidence"]) == 1
    assert "Namespace was not provided" in result["missing_evidence"][0]
    assert result["runbooks_summary"] == _RUNBOOK_SUMMARY


@pytest.mark.anyio
async def test_missing_credentials_returns_before_calling_the_model(monkeypatch):
    _patch_common(monkeypatch)

    async def _none(_purpose):
        return None

    monkeypatch.setattr(investigate_mod.SecretStore, "fetch_payload", _none)
    monkeypatch.setattr(
        investigate_mod,
        "get_llm",
        lambda _key: (_ for _ in ()).throw(
            AssertionError("The model must not run without credentials")
        ),
    )

    result = await investigate_mod.investigate(_state())

    assert result["evidence"] == []
    assert result["missing_evidence"] == ["Kubernetes cluster is not configured."]


@pytest.mark.anyio
async def test_tool_call_budget_is_enforced(monkeypatch):
    _patch_common(monkeypatch)
    monkeypatch.setattr(investigate_mod, "_MAX_TOOL_CALLS", 2)
    monkeypatch.setattr(
        investigate_mod, "get_events", lambda _ns: _ok("warning event")
    )

    model = _FakeToolCallingModel(
        [
            _call("get_events", {"namespace": "production"}, "call-1"),
            _call("get_events", {"namespace": "production"}, "call-2"),
            _call("get_events", {"namespace": "production"}, "call-3"),
            AIMessage(content="done"),
        ]
    )
    monkeypatch.setattr(investigate_mod, "get_llm", lambda _key: model)

    result = await investigate_mod.investigate(_state())

    assert len(result["evidence"]) == 2
    assert any(
        "stopped after 2 tool calls" in item
        for item in result["missing_evidence"]
    )


@pytest.mark.anyio
async def test_model_with_no_tool_calls_reports_missing_evidence(monkeypatch):
    _patch_common(monkeypatch)

    model = _FakeToolCallingModel(
        [AIMessage(content="I do not need any tools.")]
    )
    monkeypatch.setattr(investigate_mod, "get_llm", lambda _key: model)

    result = await investigate_mod.investigate(_state())

    assert result["evidence"] == []
    assert result["missing_evidence"] == [
        "The model did not request any Kubernetes evidence tools."
    ]
