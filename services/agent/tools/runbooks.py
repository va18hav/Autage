"""Deterministic runbook retrieval.

Runbooks are selected by exact service ownership and incident keywords, then
bounded sections are returned to the diagnosis prompt. The model never chooses
which runbook or section to load.
"""

from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from services.agent.playbooks import IncidentType
from services.db.database import async_session_factory
from services.db.models.runbooks import Runbook

MAX_RUNBOOKS = 3
MAX_SECTIONS_PER_RUNBOOK = 3
MAX_SECTION_CHARS = 4_000
MAX_TOTAL_CHARS = 14_000

_INCIDENT_KEYWORDS: dict[str, set[str]] = {
    IncidentType.CRASH_LOOP.value: {
        "crash",
        "crashloop",
        "crashloopbackoff",
        "oom",
        "oomkill",
        "oomkilled",
        "restart",
        "exit code 137",
        "memory",
    },
    IncidentType.BAD_DEPLOYMENT.value: {
        "bad deployment",
        "deploy",
        "deployment",
        "release",
        "rollback",
        "rollout",
        "revert",
        "5xx",
        "error rate",
    },
}

_SECTION_KEYWORDS: dict[str, set[str]] = {
    IncidentType.CRASH_LOOP.value: {
        "crash",
        "restart",
        "oom",
        "memory",
        "logs",
        "mitigation",
        "rollback",
        "recovery",
        "resolution",
        "verify",
    },
    IncidentType.BAD_DEPLOYMENT.value: {
        "rollback",
        "rollout",
        "deploy",
        "revert",
        "mitigation",
        "error",
        "5xx",
        "recovery",
        "resolution",
        "verify",
    },
}


def _normalise(value: Any) -> str:
    return str(value or "").strip().casefold()


def _runbook_terms(runbook: Runbook) -> List[str]:
    terms = [
        _normalise(runbook.title),
        _normalise(runbook.description),
    ]
    if isinstance(runbook.triggers, list):
        terms.extend(_normalise(trigger) for trigger in runbook.triggers)
    return [term for term in terms if term]


def _score_runbook(
    runbook: Runbook,
    service: Optional[str],
    incident_type: str,
) -> int:
    keywords = _INCIDENT_KEYWORDS.get(incident_type, set())
    score = 0

    if service and runbook.service and _normalise(runbook.service) == _normalise(service):
        score += 100

    terms = _runbook_terms(runbook)
    text = " ".join(terms)
    matching_keywords = {keyword for keyword in keywords if keyword in text}
    score += len(matching_keywords) * 20

    return score


def _score_section(
    heading: str,
    content: str,
    incident_type: str,
) -> int:
    keywords = _SECTION_KEYWORDS.get(incident_type, set())
    text = f"{_normalise(heading)} {_normalise(content)}"
    return sum(1 for keyword in keywords if keyword in text)


def _truncate(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit] + "\n...[section truncated]", True


async def find_runbooks_for_incident(
    service: Optional[str],
    incident_type: str,
    max_runbooks: int = MAX_RUNBOOKS,
) -> List[Dict[str, Any]]:
    """Return a small, bounded set of runbooks relevant to the incident."""
    async with async_session_factory() as db:
        result = await db.execute(
            select(Runbook)
            .options(selectinload(Runbook.sections))
            .limit(200)
        )
        runbooks = result.scalars().all()

    ranked = []
    for runbook in runbooks:
        score = _score_runbook(runbook, service, incident_type)
        if score > 0:
            ranked.append((score, runbook))

    ranked.sort(
        key=lambda item: (
            item[0],
            item[1].updated_at or item[1].created_at,
        ),
        reverse=True,
    )

    matches: List[Dict[str, Any]] = []
    remaining = MAX_TOTAL_CHARS

    for score, runbook in ranked[: max(1, min(max_runbooks, MAX_RUNBOOKS))]:
        scored_sections = [
            (
                _score_section(section.heading, section.content, incident_type),
                section,
            )
            for section in runbook.sections
        ]

        relevant_sections = [
            item for item in scored_sections if item[0] > 0
        ]
        relevant_sections.sort(key=lambda item: (item[0], -item[1].order_index), reverse=True)
        selected_sections = relevant_sections[:MAX_SECTIONS_PER_RUNBOOK]

        if not selected_sections:
            selected_sections = [
                (0, section)
                for section in sorted(
                    runbook.sections,
                    key=lambda section: section.order_index,
                )[:1]
            ]

        sections = []
        for _section_score, section in selected_sections:
            if remaining <= 0:
                break
            allowed = min(MAX_SECTION_CHARS, remaining)
            content, truncated = _truncate(section.content, allowed)
            remaining -= len(content)
            sections.append(
                {
                    "order_index": section.order_index,
                    "heading": section.heading,
                    "content": content,
                    "truncated": truncated,
                }
            )

        if not sections and runbook.raw_content and remaining > 0:
            content, truncated = _truncate(runbook.raw_content, remaining)
            remaining -= len(content)
            sections.append(
                {
                    "order_index": 0,
                    "heading": "Overview",
                    "content": content,
                    "truncated": truncated,
                }
            )

        if sections:
            matches.append(
                {
                    "runbook_id": str(runbook.id),
                    "title": runbook.title,
                    "service": runbook.service,
                    "description": runbook.description,
                    "score": score,
                    "sections": sections,
                }
            )

    return matches
