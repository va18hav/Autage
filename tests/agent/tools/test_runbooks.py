import pytest

import services.agent.tools.runbooks as rb_tools_mod
from services.agent.tools.runbooks import get_runbook_sections, list_runbooks
from services.db.models.runbooks import Runbook, RunbookSection
from tests.conftest import InMemoryAsyncSession


@pytest.mark.anyio
async def test_list_runbooks_and_get_runbook_sections(monkeypatch):
    session = InMemoryAsyncSession()
    monkeypatch.setattr(rb_tools_mod, "async_session_factory", session.factory)

    rb = Runbook(
        title="Auth OOMKill Runbook",
        service="auth-service",
        raw_content="# Auth OOM\n## Rollback\nUndo deployment",
    )
    session.add(rb)
    sec0 = RunbookSection(
        runbook=rb,
        order_index=0,
        heading="Rollback",
        content="kubectl rollout undo deployment/auth-service -n production",
    )
    session.add(sec0)

    # 1. Tool 1 returns only titles and section headings (never section content)
    inventory = await list_runbooks()
    assert len(inventory) == 1
    assert inventory[0]["runbook_title"] == "Auth OOMKill Runbook"
    assert inventory[0]["sections"] == [{"order_index": 0, "heading": "Rollback"}]
    assert "content" not in inventory[0]["sections"][0]

    # 2. Tool 2 fetches full content for requested section and reports error on missing section
    assert await get_runbook_sections([]) == []

    sections = await get_runbook_sections(
        [
            {"runbook_title": "Auth OOMKill Runbook", "section_order_index": 0},
            {"runbook_title": "Auth OOMKill Runbook", "section_order_index": 99},
        ]
    )
    assert len(sections) == 2
    assert sections[0]["error"] is None
    assert "kubectl rollout undo" in sections[0]["content"]
    assert sections[1]["error"] is not None
    assert sections[1]["content"] is None
