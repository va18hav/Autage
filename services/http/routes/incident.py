import json
import asyncio

from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Request, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from services.db.database import get_db_session
from services.db.models.incident import Incident, IncidentStatus
from services.http.schemas.incident import IncidentDetailResponse, IncidentListItemResponse

router = APIRouter(prefix="/incidents", tags=["Incidents"])

@router.get(
    "",
    response_model=List[IncidentListItemResponse],
    summary="List incidents sorted by the most recent ones"
)
async def list_incidents(
    db: AsyncSession = Depends(get_db_session)
):

    query = select(Incident).order_by(Incident.created_at.desc())
    result = await db.execute(query)
    incidents = result.scalars().all()
    return incidents

@router.get("/{incident_id}", response_model=IncidentDetailResponse)
async def get_incident(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db_session)
):

    query = (
        select(Incident)
        .where(Incident.id == incident_id)
        .options(selectinload(Incident.steps))
    )

    result = await db.execute(query)
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found",
        )

    return incident

@router.get(
    "/{incident_id}/stream",
    summary="Stream incident agent progress in real time via SSE",
)
async def stream_incident(
    incident_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):

    incident = await db.get(Incident, incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found",
        )

    channel = f"incident:{incident_id}:events"

    async def event_generator():

        if incident.status in (IncidentStatus.COMPLETED, IncidentStatus.FAILED):
            yield f"data: {json.dumps({'type': 'incident_complete', 'status': incident.status, 'title': incident.title})}\n\n"
            return

        pubsub = request.app.state.arq_pool.pubsub()
        await pubsub.subscribe(channel)

        try:
            while True:

                if await request.is_disconnected():
                    break

                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message["type"] == "message":
                    raw_data = message["data"]
                    if isinstance(raw_data, bytes):
                        raw_data = raw_data.decode("utf-8")

                    yield f"data: {raw_data}\n\n"

                    payload = json.loads(raw_data)
                    if payload.get("type") in ("incident_complete", "incident_failed"):
                        break

                await asyncio.sleep(0.05)


        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

@router.delete(
    "/{incident_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a particular incident",
)
async def delete_incident(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    incident = await db.get(Incident, incident_id)

    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found",
        )

    await db.delete(incident)
    await db.commit()
