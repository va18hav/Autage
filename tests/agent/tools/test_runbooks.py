import pytest

import services.agent.tools.runbooks as rb_tools_mod
from services.agent.tools.runbooks import (
    fetch_runbook_sections,
    format_runbook_catalog,
    load_runbook_catalog,
)
from services.db.models.runbooks import Runbook, RunbookSection
from tests.conftest import InMemoryAsyncSession


def _add_runbook(
    session: InMemoryAsyncSession,
    *,
    title: str,
    service: str | None,
    triggers: list[str] | None = None,
    sections: list[tuple[str, str]] | None = None,
    raw_content: str | None = None,
) -> Runbook:
    runbook = Runbook(
        title=title,
        service=service,
        triggers=triggers,
        raw_content=raw_content or f"# {title}",
    )
    session.add(runbook)
    for order_index, (heading, content) in enumerate(sections or []):
        session.add(
            RunbookSection(
                runbook=runbook,
                order_index=order_index,
                heading=heading,
                content=content,
            )
        )
    return runbook


@pytest.mark.anyio
async def test_catalog_lists_titles_and_headings_without_content(monkeypatch):
    session = InMemoryAsyncSession()
    monkeypatch.setattr(rb_tools_mod, "async_session_factory", session.factory)

    _add_runbook(
        session,
        title="Auth OOMKill Runbook",
        service="auth-service",
        triggers=["OOMKilled"],
        sections=[
            ("Rollback", "Run kubectl rollout undo deployment/auth-service"),
            ("Verify recovery", "Watch restarts for ten minutes"),
        ],
    )
    _add_runbook(
        session,
        title="Billing notes",
        service="billing-service",
        sections=[("Overview", "Invoice generation steps")],
    )

    catalog = await load_runbook_catalog("auth-service", "crash_loop")

    assert [entry["title"] for entry in catalog] == [
        "Auth OOMKill Runbook",
        "Billing notes",
    ]
    auth = catalog[0]
    assert auth["runbook_id"]
    assert [(section["index"], section["heading"]) for section in auth["sections"]] == [
        (0, "Rollback"),
        (1, "Verify recovery"),
    ]

    rendered = format_runbook_catalog(catalog)
    assert "Auth OOMKill Runbook" in rendered
    assert "0. Rollback" in rendered
    assert "kubectl rollout undo" not in rendered
    assert "Invoice generation" not in rendered


@pytest.mark.anyio
async def test_catalog_ranks_service_match_before_generic_match(monkeypatch):
    session = InMemoryAsyncSession()
    monkeypatch.setattr(rb_tools_mod, "async_session_factory", session.factory)

    _add_runbook(
        session,
        title="Generic OOMKilled recovery",
        service="payments-service",
        triggers=["OOMKilled"],
        sections=[("Recovery", "Restart the workload")],
    )
    _add_runbook(
        session,
        title="Checkout runbook",
        service="checkout-service",
        sections=[("Overview", "General operating notes")],
    )

    catalog = await load_runbook_catalog("checkout-service", "crash_loop")

    assert [entry["title"] for entry in catalog] == [
        "Checkout runbook",
        "Generic OOMKilled recovery",
    ]


@pytest.mark.anyio
async def test_catalog_caps_entries_but_keeps_unmatched_runbooks(monkeypatch):
    session = InMemoryAsyncSession()
    monkeypatch.setattr(rb_tools_mod, "async_session_factory", session.factory)

    for index in range(5):
        _add_runbook(
            session,
            title=f"General runbook {index}",
            service=f"service-{index}",
            sections=[("Overview", "General notes")],
        )

    catalog = await load_runbook_catalog(
        None,
        "other",
        max_runbooks=3,
    )

    assert len(catalog) == 3
    assert all(entry["sections"] for entry in catalog)


@pytest.mark.anyio
async def test_catalog_exposes_raw_content_as_overview(monkeypatch):
    session = InMemoryAsyncSession()
    monkeypatch.setattr(rb_tools_mod, "async_session_factory", session.factory)

    _add_runbook(
        session,
        title="Unparsed runbook",
        service="auth-service",
        sections=[],
        raw_content="# Rollback\nUndo the deployment.",
    )

    catalog = await load_runbook_catalog("auth-service", "crash_loop")

    assert catalog[0]["sections"] == [{"index": 0, "heading": "Overview"}]

    result = await fetch_runbook_sections(catalog[0]["runbook_id"], [0])

    assert result["ok"] is True
    assert result["sections"] == [
        {
            "index": 0,
            "heading": "Overview",
            "content": "# Rollback\nUndo the deployment.",
            "truncated": False,
        }
    ]
    # Content lives in `sections`; `output` is only a short status line.
    assert "Undo the deployment." not in result["output"]


@pytest.mark.anyio
async def test_fetch_returns_only_requested_sections(monkeypatch):
    session = InMemoryAsyncSession()
    monkeypatch.setattr(rb_tools_mod, "async_session_factory", session.factory)

    runbook = _add_runbook(
        session,
        title="Auth runbook",
        service="auth-service",
        sections=[
            ("Rollback", "Undo the deployment."),
            ("Database pool", "Tune the connection pool."),
            ("Verify recovery", "Watch restarts."),
        ],
    )

    result = await fetch_runbook_sections(str(runbook.id), [2, 0])

    assert result["ok"] is True
    assert [section["heading"] for section in result["sections"]] == [
        "Rollback",
        "Verify recovery",
    ]
    assert [section["content"] for section in result["sections"]] == [
        "Undo the deployment.",
        "Watch restarts.",
    ]
    assert "Tune the connection pool." not in result["output"]


@pytest.mark.anyio
async def test_fetch_rejects_unknown_runbook_and_bad_index(monkeypatch):
    session = InMemoryAsyncSession()
    monkeypatch.setattr(rb_tools_mod, "async_session_factory", session.factory)

    runbook = _add_runbook(
        session,
        title="Auth runbook",
        service="auth-service",
        sections=[("Rollback", "Undo the deployment.")],
    )

    missing = await fetch_runbook_sections("not-a-uuid", [0])
    assert missing["ok"] is False
    assert "Unknown runbook_id" in missing["error"]

    bad_index = await fetch_runbook_sections(str(runbook.id), [4])
    assert bad_index["ok"] is False
    assert "Valid indexes" in bad_index["error"]


@pytest.mark.anyio
async def test_fetch_rejects_too_many_sections(monkeypatch):
    session = InMemoryAsyncSession()
    monkeypatch.setattr(rb_tools_mod, "async_session_factory", session.factory)

    runbook = _add_runbook(
        session,
        title="Auth runbook",
        service="auth-service",
        sections=[
            ("One", "First"),
            ("Two", "Second"),
            ("Three", "Third"),
            ("Four", "Fourth"),
        ],
    )

    result = await fetch_runbook_sections(str(runbook.id), [0, 1, 2, 3])

    assert result["ok"] is False
    assert "at most 3 sections" in result["error"]


@pytest.mark.anyio
async def test_fetch_caps_section_content(monkeypatch):
    session = InMemoryAsyncSession()
    monkeypatch.setattr(rb_tools_mod, "async_session_factory", session.factory)

    runbook = _add_runbook(
        session,
        title="Crash loop runbook",
        service="auth-service",
        sections=[("Logs", "x" * 10_000)],
    )

    result = await fetch_runbook_sections(str(runbook.id), [0])

    section = result["sections"][0]
    assert section["truncated"] is True
    assert len(section["content"]) <= rb_tools_mod.MAX_SECTION_CHARS + 40
    assert result["truncated"] is True
