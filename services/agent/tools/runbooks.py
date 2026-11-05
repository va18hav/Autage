"""Two-step runbook retrieval.

Step 1 builds a compact catalog of runbook titles and section headings, ranked
deterministically by service, incident type, and query terms. Step 2 fetches
only the sections an LLM asks for. The model chooses what to read, but it never
issues arbitrary database queries or edits runbook content.

Keeping section bodies out of the first step makes the context proportional to
the catalog, not to the total size of every uploaded runbook.
"""

import re
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from services.agent.incidents import IncidentType
from services.db.database import async_session_factory
from services.db.models.runbooks import Runbook

MAX_CATALOG_RUNBOOKS = 40
MAX_CATALOG_SECTIONS = 400
MAX_CATALOG_DESCRIPTION_CHARS = 300
MAX_CATALOG_CHARS = 14_000
MAX_FETCH_SECTIONS = 3
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

_QUERY_STOPWORDS = {
    "about",
    "after",
    "again",
    "against",
    "also",
    "and",
    "are",
    "been",
    "before",
    "being",
    "but",
    "can",
    "could",
    "did",
    "does",
    "for",
    "from",
    "had",
    "has",
    "have",
    "here",
    "how",
    "into",
    "its",
    "just",
    "not",
    "only",
    "our",
    "over",
    "should",
    "than",
    "that",
    "the",
    "their",
    "then",
    "there",
    "this",
    "was",
    "were",
    "what",
    "when",
    "which",
    "will",
    "with",
    "would",
    "your",
}


def _normalise(value: Any) -> str:
    return str(value or "").strip().casefold()


def _query_terms(query: Optional[str]) -> set[str]:
    """Turn a free-text query into meaningful lowercase terms."""
    if not query:
        return set()
    words = re.findall(r"[a-z0-9]+", str(query).casefold())
    return {
        word
        for word in words
        if len(word) >= 3 and word not in _QUERY_STOPWORDS
    }


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
    query_terms: set[str],
) -> int:
    keywords = _INCIDENT_KEYWORDS.get(incident_type, set())
    score = 0

    if (
        service
        and runbook.service
        and _normalise(runbook.service) == _normalise(service)
    ):
        score += 100

    terms = _runbook_terms(runbook)
    section_text = " ".join(
        f"{_normalise(section.heading)} {_normalise(section.content)}"
        for section in runbook.sections
    )
    text = " ".join(terms + [section_text])
    matching_keywords = {keyword for keyword in keywords if keyword in text}
    score += len(matching_keywords) * 20
    score += sum(1 for term in query_terms if term in text) * 15

    return score


def _ordered_sections(runbook: Runbook) -> List[Any]:
    return sorted(runbook.sections, key=lambda section: section.order_index)


def _catalog_sections(runbook: Runbook) -> List[Dict[str, Any]]:
    """Return headings with stable, zero-based indexes for later fetching."""
    sections = _ordered_sections(runbook)
    if sections:
        return [
            {"index": index, "heading": section.heading}
            for index, section in enumerate(sections)
        ]

    # Some uploaded runbooks may not have parsed sections yet. Expose the raw
    # content as a single synthetic "Overview" section so it is still readable.
    if runbook.raw_content:
        return [{"index": 0, "heading": "Overview"}]
    return []


async def load_runbook_catalog(
    service: Optional[str],
    incident_type: str,
    *,
    query: Optional[str] = None,
    max_runbooks: int = MAX_CATALOG_RUNBOOKS,
) -> List[Dict[str, Any]]:
    """Return titles and section headings only, ordered by likely relevance.

    All accessible runbooks can appear in the catalog (up to a hard cap), not
    just exact keyword matches. The LLM makes the final section choice.
    """
    query_terms = _query_terms(query)

    async with async_session_factory() as db:
        result = await db.execute(
            select(Runbook)
            .options(selectinload(Runbook.sections))
            .limit(200)
        )
        runbooks = result.scalars().all()

    ranked = [
        (
            _score_runbook(runbook, service, incident_type, query_terms),
            runbook,
        )
        for runbook in runbooks
    ]
    ranked.sort(
        key=lambda item: (
            item[0],
            item[1].updated_at or item[1].created_at,
        ),
        reverse=True,
    )

    catalog: List[Dict[str, Any]] = []
    total_sections = 0

    for score, runbook in ranked[
        : max(1, min(max_runbooks, MAX_CATALOG_RUNBOOKS))
    ]:
        section_entries = _catalog_sections(runbook)
        if not section_entries:
            continue

        remaining_sections = MAX_CATALOG_SECTIONS - total_sections
        if remaining_sections <= 0:
            break

        section_entries = section_entries[:remaining_sections]
        total_sections += len(section_entries)
        description = runbook.description or ""
        if len(description) > MAX_CATALOG_DESCRIPTION_CHARS:
            description = (
                description[:MAX_CATALOG_DESCRIPTION_CHARS] + "…"
            )

        catalog.append(
            {
                "runbook_id": str(runbook.id),
                "title": runbook.title,
                "service": runbook.service,
                "description": description or None,
                "score": score,
                "sections": section_entries,
            }
        )

    return catalog


def format_runbook_catalog(catalog: List[Dict[str, Any]]) -> str:
    """Format the heading-only catalog for a prompt or tool response."""
    if not catalog:
        return "No runbooks are available."

    lines = ["Runbook catalog (titles and section headings only):"]

    for entry in catalog:
        service = entry.get("service") or "unspecified service"
        lines.append(
            f'- runbook_id={entry["runbook_id"]} | '
            f'title="{entry["title"]}" | service={service}'
        )
        if entry.get("description"):
            lines.append(f"  description: {entry['description']}")
        lines.append("  sections:")
        for section in entry.get("sections") or []:
            lines.append(f"    {section['index']}. {section['heading']}")

    rendered: List[str] = []
    used = 0
    for line in lines:
        if used + len(line) + 1 > MAX_CATALOG_CHARS:
            rendered.append("...[catalog truncated]")
            break
        rendered.append(line)
        used += len(line) + 1

    return "\n".join(rendered)


def _truncate(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit] + "\n...[section truncated]", True


def _failure(error: str) -> Dict[str, Any]:
    return {
        "ok": False,
        "output": "",
        "error": error,
        "truncated": False,
    }


def format_runbook_sections(
    title: str,
    service: Optional[str],
    sections: List[Dict[str, Any]],
) -> str:
    """Format fetched sections for a summary or tool response."""
    blocks = [
        f"## Runbook: {title} "
        f"(service: {service or 'unspecified service'})"
    ]

    for section in sections:
        blocks.append(
            f"### {section.get('heading') or 'Untitled section'}\n"
            f"{section.get('content') or ''}"
        )

    return "\n\n".join(blocks).strip()


async def fetch_runbook_sections(
    runbook_id: str,
    section_indexes: List[int],
    *,
    max_total_chars: int = MAX_TOTAL_CHARS,
) -> Dict[str, Any]:
    """Read specific sections selected from the catalog.

    Indexes refer to the stable order shown by ``load_runbook_catalog``. Every
    identifier is validated against the database; the model cannot request
    arbitrary content or exceed the read budget.
    """
    try:
        runbook_uuid = uuid.UUID(str(runbook_id))
    except (AttributeError, TypeError, ValueError):
        return _failure(
            f"Unknown runbook_id '{runbook_id}'. "
            "Use an id from the runbook catalog."
        )

    indexes: List[int] = []
    for value in section_indexes or []:
        if isinstance(value, bool):
            return _failure("section_indexes must be a list of integers.")
        try:
            index = int(value)
        except (TypeError, ValueError):
            return _failure("section_indexes must be a list of integers.")
        if index not in indexes:
            indexes.append(index)

    if not indexes:
        return _failure("Provide at least one section index.")
    if len(indexes) > MAX_FETCH_SECTIONS:
        return _failure(
            f"Request at most {MAX_FETCH_SECTIONS} sections per call."
        )

    async with async_session_factory() as db:
        result = await db.execute(
            select(Runbook)
            .options(selectinload(Runbook.sections))
            .where(Runbook.id == runbook_uuid)
        )
        runbook = result.scalar_one_or_none()

    if runbook is None:
        return _failure(
            f"Runbook '{runbook_id}' was not found. "
            "Use an id from the runbook catalog."
        )

    sections = _ordered_sections(runbook)
    if sections:
        headings = [section.heading for section in sections]
        contents = [section.content for section in sections]
    elif runbook.raw_content:
        headings = ["Overview"]
        contents = [runbook.raw_content]
    else:
        return _failure(f"Runbook '{runbook.title}' has no readable sections.")

    invalid = [
        index for index in indexes if index < 0 or index >= len(headings)
    ]
    if invalid:
        return _failure(
            f"Unknown section index(es) {invalid} for runbook "
            f"'{runbook.title}'. Valid indexes: {list(range(len(headings)))}."
        )

    remaining = max(0, min(max_total_chars, MAX_TOTAL_CHARS))
    selected: List[Dict[str, Any]] = []
    truncated = False

    for index in sorted(indexes):
        if remaining <= 0:
            truncated = True
            break

        allowed = min(MAX_SECTION_CHARS, remaining)
        content, item_truncated = _truncate(contents[index], allowed)
        remaining -= len(content)
        truncated = truncated or item_truncated
        selected.append(
            {
                "index": index,
                "heading": headings[index],
                "content": content,
                "truncated": item_truncated,
            }
        )

    return {
        "ok": True,
        "output": (
            f"Read {len(selected)} section(s) from "
            f"'{runbook.title}'. Use the structured sections field for content."
        ),
        "error": None,
        "truncated": truncated,
        "runbook_id": str(runbook.id),
        "title": runbook.title,
        "service": runbook.service,
        "sections": selected,
    }
