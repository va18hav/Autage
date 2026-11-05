from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage

import services.agent.nodes.search_runbook as search_runbook_mod
import services.agent.nodes.trace_step as trace_step_mod
import services.agent.tools.runbooks as rb_tools_mod
from services.agent.incidents import IncidentType
from services.db.models.runbooks import Runbook, RunbookSection
from tests.conftest import InMemoryAsyncSession

_RUNBOOK_ID = "11111111-1111-1111-1111-111111111111"
_CATALOG = [
    {
        "runbook_id": _RUNBOOK_ID,
        "title": "Auth OOM runbook",
        "service": "auth-service",
        "description": "Crash-loop recovery steps.",
        "score": 120,
        "sections": [
            {"index": 0, "heading": "Rollback"},
            {"index": 1, "heading": "Verify recovery"},
        ],
    }
]


def _call(name: str, args: dict, call_id: str) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": name,
                "args": args,
                "id": call_id,
                "type": "tool_call",
            }
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
        "missing_evidence": [],
    }
    state.update(overrides)
    return state


def _patch_common(monkeypatch, catalog=None):
    session = InMemoryAsyncSession()
    monkeypatch.setattr(trace_step_mod, "async_session_factory", session.factory)

    async def _load_catalog(**_kwargs):
        return list(_CATALOG if catalog is None else catalog)

    monkeypatch.setattr(
        search_runbook_mod, "load_runbook_catalog", _load_catalog
    )


@pytest.mark.anyio
async def test_model_selects_sections_and_node_builds_summary(monkeypatch):
    _patch_common(monkeypatch)
    calls = []

    async def _fetch(runbook_id, section_indexes, *, max_total_chars):
        calls.append((runbook_id, section_indexes, max_total_chars))
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
                    "index": index,
                    "heading": (
                        "Rollback"
                        if index == 0
                        else "Verify recovery"
                    ),
                    "content": (
                        "Roll back the deployment."
                        if index == 0
                        else "Watch restarts for ten minutes."
                    ),
                    "truncated": False,
                }
                for index in section_indexes
            ],
        }

    monkeypatch.setattr(
        search_runbook_mod, "fetch_runbook_sections", _fetch
    )

    model = _FakeToolCallingModel(
        [
            _call(
                "read_runbook_sections",
                {
                    "runbook_id": _RUNBOOK_ID,
                    "section_indexes": [0, 1],
                },
                "call-1",
            ),
            AIMessage(content="Selected the recovery sections."),
        ]
    )
    monkeypatch.setattr(search_runbook_mod, "get_llm", lambda _key: model)

    result = await search_runbook_mod.search_runbook(_state())

    assert model.tool_names == ["read_runbook_sections"]
    assert calls == [(_RUNBOOK_ID, [0, 1], 14_000)]

    prompt = model.messages[0][1].content
    assert "Auth OOM runbook" in prompt
    assert "0. Rollback" in prompt
    assert "Roll back the deployment." not in prompt

    assert result["missing_evidence"] == []
    assert "Auth OOM runbook" in result["runbooks_summary"]
    assert "### Rollback" in result["runbooks_summary"]
    assert "Roll back the deployment." in result["runbooks_summary"]
    assert "### Verify recovery" in result["runbooks_summary"]


@pytest.mark.anyio
async def test_node_reads_real_catalog_and_fetches_selected_section(monkeypatch):
    session = InMemoryAsyncSession()
    monkeypatch.setattr(trace_step_mod, "async_session_factory", session.factory)
    monkeypatch.setattr(
        rb_tools_mod, "async_session_factory", session.factory
    )

    runbook = Runbook(
        title="Auth OOM runbook",
        service="auth-service",
        triggers=["OOMKilled"],
        raw_content="# Auth OOM runbook",
    )
    session.add(runbook)
    session.add(
        RunbookSection(
            runbook=runbook,
            order_index=0,
            heading="Rollback",
            content="Roll back the deployment.",
        )
    )

    model = _FakeToolCallingModel(
        [
            _call(
                "read_runbook_sections",
                {
                    "runbook_id": str(runbook.id),
                    "section_indexes": [0],
                },
                "call-1",
            ),
            AIMessage(content="Selected the rollback section."),
        ]
    )
    monkeypatch.setattr(search_runbook_mod, "get_llm", lambda _key: model)

    result = await search_runbook_mod.search_runbook(_state())

    assert "Auth OOM runbook" in result["runbooks_summary"]
    assert "### Rollback" in result["runbooks_summary"]
    assert "Roll back the deployment." in result["runbooks_summary"]
    assert result["missing_evidence"] == []


@pytest.mark.anyio
async def test_no_catalog_skips_the_model(monkeypatch):
    _patch_common(monkeypatch, catalog=[])

    def _forbidden(_key):
        raise AssertionError("The model must not run without a catalog")

    monkeypatch.setattr(search_runbook_mod, "get_llm", _forbidden)

    result = await search_runbook_mod.search_runbook(_state())

    assert result["runbooks_summary"] == ""
    assert result["missing_evidence"] == []


@pytest.mark.anyio
async def test_model_configuration_failure_becomes_missing_evidence(monkeypatch):
    _patch_common(monkeypatch)

    def _raise(_key):
        raise RuntimeError("no model configured")

    monkeypatch.setattr(search_runbook_mod, "get_llm", _raise)

    result = await search_runbook_mod.search_runbook(_state())

    assert result["runbooks_summary"] == ""
    assert any(
        "Runbook selection model unavailable" in item
        for item in result["missing_evidence"]
    )


@pytest.mark.anyio
async def test_tool_call_budget_is_enforced(monkeypatch):
    _patch_common(monkeypatch)
    monkeypatch.setattr(search_runbook_mod, "_MAX_TOOL_CALLS", 2)
    fetches = []

    async def _fetch(runbook_id, section_indexes, *, max_total_chars):
        fetches.append(section_indexes)
        return {
            "ok": True,
            "output": "section",
            "error": None,
            "truncated": False,
            "runbook_id": runbook_id,
            "title": "Auth OOM runbook",
            "service": "auth-service",
            "sections": [
                {
                    "index": index,
                    "heading": "Rollback",
                    "content": "Roll back.",
                    "truncated": False,
                }
                for index in section_indexes
            ],
        }

    monkeypatch.setattr(
        search_runbook_mod, "fetch_runbook_sections", _fetch
    )

    model = _FakeToolCallingModel(
        [
            _call(
                "read_runbook_sections",
                {"runbook_id": _RUNBOOK_ID, "section_indexes": [0]},
                "call-1",
            ),
            _call(
                "read_runbook_sections",
                {"runbook_id": _RUNBOOK_ID, "section_indexes": [1]},
                "call-2",
            ),
            _call(
                "read_runbook_sections",
                {"runbook_id": _RUNBOOK_ID, "section_indexes": [0]},
                "call-3",
            ),
        ]
    )
    monkeypatch.setattr(search_runbook_mod, "get_llm", lambda _key: model)

    result = await search_runbook_mod.search_runbook(_state())

    assert len(fetches) == 2
    assert any(
        "stopped after 2 tool calls" in item
        for item in result["missing_evidence"]
    )


@pytest.mark.anyio
async def test_duplicate_sections_are_not_repeated(monkeypatch):
    _patch_common(monkeypatch)

    async def _fetch(runbook_id, section_indexes, *, max_total_chars):
        return {
            "ok": True,
            "output": "section",
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
        search_runbook_mod, "fetch_runbook_sections", _fetch
    )

    model = _FakeToolCallingModel(
        [
            _call(
                "read_runbook_sections",
                {"runbook_id": _RUNBOOK_ID, "section_indexes": [0]},
                "call-1",
            ),
            _call(
                "read_runbook_sections",
                {"runbook_id": _RUNBOOK_ID, "section_indexes": [0]},
                "call-2",
            ),
            AIMessage(content="Done."),
        ]
    )
    monkeypatch.setattr(search_runbook_mod, "get_llm", lambda _key: model)

    result = await search_runbook_mod.search_runbook(_state())

    assert result["runbooks_summary"].count("### Rollback") == 1


@pytest.mark.anyio
async def test_failed_fetch_is_missing_evidence(monkeypatch):
    _patch_common(monkeypatch)

    async def _fetch(_runbook_id, _section_indexes, *, max_total_chars):
        return {
            "ok": False,
            "output": "",
            "error": "Unknown section index(es) [9].",
            "truncated": False,
        }

    monkeypatch.setattr(
        search_runbook_mod, "fetch_runbook_sections", _fetch
    )

    model = _FakeToolCallingModel(
        [
            _call(
                "read_runbook_sections",
                {"runbook_id": _RUNBOOK_ID, "section_indexes": [9]},
                "call-1",
            ),
            AIMessage(content="I could not read that section."),
        ]
    )
    monkeypatch.setattr(search_runbook_mod, "get_llm", lambda _key: model)

    result = await search_runbook_mod.search_runbook(_state())

    assert result["runbooks_summary"] == ""
    assert any(
        "Runbook section read failed" in item
        for item in result["missing_evidence"]
    )


@pytest.mark.anyio
async def test_model_turn_budget_is_enforced(monkeypatch):
    _patch_common(monkeypatch)
    monkeypatch.setattr(search_runbook_mod, "_MAX_TOOL_ROUNDS", 1)

    async def _fetch(runbook_id, _section_indexes, *, max_total_chars):
        return {
            "ok": True,
            "output": "section",
            "error": None,
            "truncated": False,
            "runbook_id": runbook_id,
            "title": "Auth OOM runbook",
            "service": "auth-service",
            "sections": [],
        }

    monkeypatch.setattr(
        search_runbook_mod, "fetch_runbook_sections", _fetch
    )

    model = _FakeToolCallingModel(
        [
            _call(
                "read_runbook_sections",
                {"runbook_id": _RUNBOOK_ID, "section_indexes": [0]},
                "call-1",
            )
        ]
    )
    monkeypatch.setattr(search_runbook_mod, "get_llm", lambda _key: model)

    result = await search_runbook_mod.search_runbook(_state())

    assert any(
        "stopped after 1 model turns" in item
        for item in result["missing_evidence"]
    )
