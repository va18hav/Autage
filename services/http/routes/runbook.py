from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from services.db.database import get_db_session
from services.db.models.runbooks import Runbook, RunbookSection
from services.http.schemas.runbook import (
    RunbookCreate,
    RunbookDetailResponse,
    RunbookListItemResponse,
)

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


@router.get(
    "",
    response_model=List[RunbookListItemResponse],
    summary="List runbooks, most recent first",
)
async def list_runbooks(db: AsyncSession = Depends(get_db_session)):
    result = await db.execute(
        select(Runbook).order_by(Runbook.created_at.desc())
    )
    return result.scalars().all()


@router.get(
    "/{runbook_id}",
    response_model=RunbookDetailResponse,
    summary="Runbook detail with ordered sections",
)
async def get_runbook(
    runbook_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(
        select(Runbook)
        .where(Runbook.id == runbook_id)
        .options(selectinload(Runbook.sections))
    )
    runbook = result.scalar_one_or_none()

    if not runbook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Runbook {runbook_id} not found",
        )

    return runbook


@router.delete(
    "/{runbook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a runbook (sections cascade)",
)
async def delete_runbook(
    runbook_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    runbook = await db.get(Runbook, runbook_id)
    if not runbook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Runbook {runbook_id} not found",
        )

    await db.delete(runbook)
    await db.commit()
