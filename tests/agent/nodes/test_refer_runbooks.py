from uuid import uuid4

import pytest

import services.agent.nodes.refer_runbooks as refer_rb_mod
import services.agent.nodes.trace_step as trace_step_mod
from services.agent.nodes.refer_runbooks import (
    SectionRequest,
    SectionsSelection,
    refer_runbooks,
)
from tests.conftest import InMemoryAsyncSession


class _FakeStructured:
    def __init__(self, resp):
        self._resp = resp

    async def ainvoke(self, _prompt):
        return self._resp


class _FakeLLM:
    def __init__(self, selection, summary_text):
        self._selection = selection
        self._summary_text = summary_text

    def with_structured_output(self, _schema):
        return _FakeStructured(self._selection)

    async def ainvoke(self, _prompt):
        return self._summary_text


@pytest.mark.anyio
async def test_refer_runbooks_two_pass_retrieval_and_empty_fallbacks(monkeypatch):
    session = InMemoryAsyncSession()
    monkeypatch.setattr(trace_step_mod, "async_session_factory", session.factory)

    base_state = {
        "incident_id": str(uuid4()),
        "incident_title": "Auth Service OOM",
        "severity": "P1",
        "summary": "OOMKilled",
        "logs_summary": "Exit code 137",
    }

    # Case 1: Empty runbook inventory returns ""
    async def _empty_list():
        return []

    monkeypatch.setattr(refer_rb_mod, "list_runbooks", _empty_list)
    monkeypatch.setattr(refer_rb_mod, "get_llm", lambda _step: None)
    assert await refer_runbooks(base_state) == {"runbooks_summary": ""}

    # Case 2: Non-empty inventory + section selection -> summarizes retrieved sections
    async def _populated_list():
        return [
            {
                "runbook_title": "Auth OOM Runbook",
                "service": "auth-service",
                "sections": [{"order_index": 0, "heading": "Rollback"}],
            }
        ]

    async def _fake_get_sections(selections):
        return [
            {
                "requested": selections[0],
                "heading": "Rollback",
                "content": "kubectl rollout undo deployment/auth-service -n production",
                "error": None,
            }
        ]

    monkeypatch.setattr(refer_rb_mod, "list_runbooks", _populated_list)
    monkeypatch.setattr(refer_rb_mod, "get_runbook_sections", _fake_get_sections)

    selection = SectionsSelection(
        reasoning="Relevant rollback section",
        sections=[SectionRequest(runbook_title="Auth OOM Runbook", section_order_index=0)],
    )
    fake_llm = _FakeLLM(selection, "Roll back deployment/auth-service in production.")
    monkeypatch.setattr(refer_rb_mod, "get_llm", lambda _step: fake_llm)

    res = await refer_runbooks(base_state)
    assert res["runbooks_summary"] == "Roll back deployment/auth-service in production."
