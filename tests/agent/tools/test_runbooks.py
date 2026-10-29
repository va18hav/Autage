import pytest

import services.agent.tools.runbooks as rb_tools_mod
from services.agent.tools.runbooks import find_runbooks_for_incident
from services.db.models.runbooks import Runbook, RunbookSection
from tests.conftest import InMemoryAsyncSession


def _add_runbook(
    session: InMemoryAsyncSession,
    *,
    title: str,
    service: str | None,
    triggers: list[str] | None = None,
    sections: list[tuple[str, str]] | None = None,
) -> Runbook:
    runbook = Runbook(
        title=title,
        service=service,
        triggers=triggers,
        raw_content=f"# {title}",
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
async def test_matches_service_and_returns_only_relevant_sections(monkeypatch):
    session = InMemoryAsyncSession()
    monkeypatch.setattr(rb_tools_mod, "async_session_factory", session.factory)

    _add_runbook(
        session,
        title="Auth OOMKill Runbook",
        service="auth-service",
        triggers=["OOMKilled"],
        sections=[
            ("Rollback", "kubectl rollout undo deployment/auth-service -n production"),
            ("Database pool", "Unrelated database connection pool tuning"),
            ("Verify recovery", "Watch restarts for ten minutes"),
        ],
    )

    matches = await find_runbooks_for_incident("auth-service", "crash_loop")

    assert len(matches) == 1
    match = matches[0]
    assert match["title"] == "Auth OOMKill Runbook"
    assert match["score"] >= 100
    assert {section["heading"] for section in match["sections"]} == {
        "Rollback",
        "Verify recovery",
    }


@pytest.mark.anyio
async def test_exact_service_match_outranks_keyword_match(monkeypatch):
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

    matches = await find_runbooks_for_incident("checkout-service", "crash_loop")

    assert [match["title"] for match in matches] == [
        "Checkout runbook",
        "Generic OOMKilled recovery",
    ]


@pytest.mark.anyio
async def test_returns_at_most_three_runbooks(monkeypatch):
    session = InMemoryAsyncSession()
    monkeypatch.setattr(rb_tools_mod, "async_session_factory", session.factory)

    for index in range(5):
        _add_runbook(
            session,
            title=f"Rollout runbook {index}",
            service=f"service-{index}",
            triggers=["rollback"],
            sections=[("Rollback", "Undo the rollout")],
        )

    matches = await find_runbooks_for_incident(None, "bad_deployment")

    assert len(matches) == 3


@pytest.mark.anyio
async def test_falls_back_to_first_section_and_returns_empty_without_matches(monkeypatch):
    session = InMemoryAsyncSession()
    monkeypatch.setattr(rb_tools_mod, "async_session_factory", session.factory)

    _add_runbook(
        session,
        title="Auth deployment guide",
        service="auth-service",
        sections=[
            ("Overview", "General operating notes"),
            ("Contacts", "Who owns it"),
        ],
    )
    _add_runbook(
        session,
        title="Billing database notes",
        service="billing-service",
        sections=[("Overview", "Database maintenance")],
    )

    matches = await find_runbooks_for_incident("auth-service", "bad_deployment")

    assert len(matches) == 1
    assert matches[0]["title"] == "Auth deployment guide"
    assert [section["heading"] for section in matches[0]["sections"]] == ["Overview"]

    assert await find_runbooks_for_incident(None, "other") == []


@pytest.mark.anyio
async def test_caps_section_content(monkeypatch):
    session = InMemoryAsyncSession()
    monkeypatch.setattr(rb_tools_mod, "async_session_factory", session.factory)

    _add_runbook(
        session,
        title="Crash loop runbook",
        service="auth-service",
        sections=[("Logs", "x" * 10_000)],
    )

    matches = await find_runbooks_for_incident("auth-service", "crash_loop")

    section = matches[0]["sections"][0]
    assert section["truncated"] is True
    assert len(section["content"]) <= rb_tools_mod.MAX_SECTION_CHARS + 40
