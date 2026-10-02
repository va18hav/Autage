import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from services.config import settings
from services.db.database import get_db_session
from services.db.models.incident import Incident, IncidentStatus
from services.http.verify_webhook import verify_webhook_signature

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post(
    path="/alert",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Receive a raw monitoring alert from any provider",
)
async def receive_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    # ── 1. Read raw bytes — must happen before any parsing ───────────────────
    # HMAC verification requires the exact original bytes, not a re-serialised dict
    payload = await request.body()

    # ── 2. Verify HMAC signature ──────────────────────────────────────────────
    # Datadog, PagerDuty, GitHub all use X-Hub-Signature-256
    signature_header = request.headers.get("X-Hub-Signature-256")
    if not verify_webhook_signature(payload, signature_header, settings.WEBHOOK_SECRET):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )

    # ── 3. Parse JSON ─────────────────────────────────────────────────────────
    try:
        raw_alert: dict = json.loads(payload)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request body must be valid JSON"
        )
    # We store the entire provider payload as-is — no normalisation.
    # Each provider (Datadog, Prometheus, Sentry, PagerDuty) has a different
    # shape; the agent LLM handles parsing at triage time.

    # ── 4. Fingerprint — sha256 of sorted payload for dedup ───────────────────
    fingerprint = hashlib.sha256(
        json.dumps(raw_alert, sort_keys=True).encode()
    ).hexdigest()[:64]

    stmt = select(Incident).where(Incident.fingerprint == fingerprint)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        return{
            "message": "Incident already exists"
        }

    # ── 5. Persist and return ─────────────────────────────────────────────────
    incident = Incident(
        title="Pending triage",
        status=IncidentStatus.PENDING,
        raw_alert=raw_alert,
        fingerprint=fingerprint,
    )
    db.add(incident)
    await db.commit()
    await db.refresh(incident)

    await request.app.state.arq_pool.enqueue_job(
        "run_agent_task",
        str(incident.id),
        _job_id=f"incident:{incident.id}"
    )

    return {
        "incident_id": str(incident.id),
        "status": incident.status,
    }

