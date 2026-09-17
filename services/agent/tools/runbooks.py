from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from services.db.database import async_session_factory
from services.db.models.runbooks import Runbook


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
