import json
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from packages.common.database import get_db_session
from packages.models.incident import Incident, IncidentStatus
from packages.models.settings import AppSettings
from services.http.parsers import get_parser
from services.http.schemas.webhooks import NormalizedAlert
from services.http.security import verify_webhook_signature
from services.agent import notify_worker

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post(
    "/{provider}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Receive monitoring alert webhook",
)
async def receive_webhook(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Ingest incoming webhook alerts from monitoring providers (e.g. Prometheus Alertmanager).

    Workflow:
      1. Fetch alert_webhook_secret from AppSettings in DB.
      2. Verify HMAC signature header against the raw request body.
      3. Parse the payload into a consolidated NormalizedAlert.
      4. Handle resolution or deduplication of active incidents.
      5. Persist a new Incident row with status 'PENDING'.
      6. Return 202 Accepted immediately.
    """
    # 1. Fetch current alert_webhook_secret and github context from AppSettings
    settings_query = await db.execute(select(AppSettings).limit(1))
    settings_row = settings_query.scalars().first()

    webhook_secret = (
        settings_row.alert_webhook_secret
        if settings_row
        else "relly-super-secret-webhook-key"
    )

    # 2. Extract and verify HMAC signature
    signature = (
        request.headers.get("X-Signature-256")
        or request.headers.get("X-Hub-Signature-256")
        or request.headers.get("X-Signature")
    )

    body_bytes = await request.body()

    if not verify_webhook_signature(body_bytes, signature, webhook_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing webhook signature",
        )

    # 3. Parse JSON payload
    try:
        payload = json.loads(body_bytes.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON payload: {exc}",
        )

    # 4. Resolve parser and parse alert
    try:
        parser = get_parser(provider)
        alert: NormalizedAlert = parser.parse(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    # 5. Handle resolved alerts
    if alert.status == "resolved":
        if alert.fingerprint:
            resolve_query = await db.execute(
                select(Incident).where(
                    Incident.fingerprint == alert.fingerprint,
                    Incident.status.in_(
                        [
                            IncidentStatus.PENDING,
                            IncidentStatus.RESOLVING,
                            IncidentStatus.AWAITING_APPROVAL,
                        ]
                    ),
                )
            )
            existing_incident = resolve_query.scalars().first()
            if existing_incident:
                try:
                    existing_incident.status = IncidentStatus.RESOLVED
                    await db.commit()
                except SQLAlchemyError as exc:
                    await db.rollback()
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Database error updating incident: {exc}",
                    )
                return {
                    "status": "resolved",
                    "incident_id": str(existing_incident.id),
                    "message": f"Incident {existing_incident.id} marked as RESOLVED",
                }

        return {
            "status": "ignored",
            "message": "Alert status is 'resolved' with no active incident found",
        }

    # 6. Deduplication: check if an active incident already exists for this fingerprint
    if alert.fingerprint:
        dedup_query = await db.execute(
            select(Incident).where(
                Incident.fingerprint == alert.fingerprint,
                Incident.status.in_(
                    [
                        IncidentStatus.PENDING,
                        IncidentStatus.RESOLVING,
                        IncidentStatus.AWAITING_APPROVAL,
                    ]
                ),
            )
        )
        active_incident = dedup_query.scalars().first()
        if active_incident:
            return {
                "status": "deduplicated",
                "incident_id": str(active_incident.id),
                "message": f"Incident already actively being handled under {active_incident.id}",
            }

    # 7. Extract target repository context from AppSettings if configured
    git_repo = None
    git_branch = None
    if settings_row and settings_row.github_config:
        git_repo = settings_row.github_config.get("repo")
        git_branch = settings_row.github_config.get("default_branch", "main")

    # 8. Create new Incident row with status PENDING
    new_incident = Incident(
        id=uuid.uuid4(),
        title=alert.title,
        source=alert.source,
        status=IncidentStatus.PENDING,
        raw_alert=alert.raw_alert,
        fingerprint=alert.fingerprint,
        git_repo=git_repo,
        git_branch=git_branch,
    )

    try:
        db.add(new_incident)
        await db.commit()
        await db.refresh(new_incident)
    except SQLAlchemyError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error saving incident: {exc}",
        )

    # Wake the agent worker immediately
    notify_worker()

    return {
        "status": "accepted",
        "incident_id": str(new_incident.id),
        "title": new_incident.title,
    }
