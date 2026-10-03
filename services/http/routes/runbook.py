
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.db.database import get_db_session
from services.db.models.runbooks import Runbook, RunbookSection
from services.http.schemas.runbook import RunbookCreate, RunbookDetailResponse

router = APIRouter(prefix="/runbooks", tags=["Runbooks"])


@router.post(
    "",
    response_model=RunbookDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Store a runbook already chunked by the frontend parser",
)
async def create_runbook(
    payload: RunbookCreate,
    db: AsyncSession = Depends(get_db_session),
):
    """
    The frontend chunks .md files and sends the parsed sections, so this route
    does no parsing — it only persists (title, description, service, triggers,
    raw_content, sections).

    Replace semantics: a runbook with the same title + service is deleted and
    re-saved (idempotent upload of an edited document).
    """
    # Find a previous version of this document (service NULL-matches NULL)
    existing = (
        await db.execute(
            select(Runbook).where(
                Runbook.title == payload.title,
                Runbook.service == payload.service,
            )
        )
    ).scalar_one_or_none()

    if existing:
        await db.delete(existing)
        await db.flush()

    runbook = Runbook(
        title=payload.title,
        description=payload.description or None,
        service=payload.service,
        triggers=payload.triggers,
        raw_content=payload.raw_content,
    )
    db.add(runbook)

    # Re-normalize order_index sequentially so the ordered relationship stays tight
    for index, section in enumerate(
        sorted(payload.sections, key=lambda s: s.order_index)
    ):
        db.add(
            RunbookSection(
                runbook=runbook,
                order_index=index,
                heading=section.heading,
                content=section.content,
            )
        )

    await db.commit()
    await db.refresh(runbook)

    return runbook
