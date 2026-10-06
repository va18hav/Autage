from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from services.db.database import async_session_factory
from services.db.models.runbooks import Runbook, RunbookSection


async def list_runbooks() -> List[Dict[str, Any]]:
    """
    First tool for the refer_runbooks node: it only reveals titles —
    runbook titles and section titles/headings — never the section content,
    so the LLM must decide which sections to request explicitly.
    """
    async with async_session_factory() as db:
        result = await db.execute(
            select(Runbook).options(selectinload(Runbook.sections))
        )
        runbooks = result.scalars().all()

    return [
        {
            "runbook_title": rb.title,
            "service": rb.service,
            "sections": [
                {"order_index": s.order_index, "heading": s.heading}
                for s in rb.sections
            ],
        }
        for rb in runbooks
    ]


async def get_runbook_sections(
    selections: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Second tool for the refer_runbooks node: the LLM requests specific
    sections by (runbook_title, order_index) and gets their full content.
    """
    if not selections:
        return []

    async with async_session_factory() as db:
        fetched: List[Dict[str, Any]] = []
        for sel in selections:
            title = sel.get("runbook_title")
            order_index = sel.get("section_order_index")

            stmt = (
                select(RunbookSection)
                .join(Runbook, RunbookSection.runbook_id == Runbook.id)
                .where(
                    Runbook.title == title,
                    RunbookSection.order_index == order_index,
                )
            )
            section = (await db.execute(stmt)).scalar_one_or_none()

            if section is None:
                fetched.append(
                    {
                        "requested": {"runbook_title": title, "section_order_index": order_index},
                        "heading": None,
                        "content": None,
                        "error": "Section not found for the requested runbook/order_index",
                    }
                )
                continue

            fetched.append(
                {
                    "requested": {"runbook_title": title, "section_order_index": order_index},
                    "heading": section.heading,
                    "content": section.content,
                    "error": None,
                }
            )

    return fetched
