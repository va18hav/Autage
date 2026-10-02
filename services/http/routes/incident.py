import json
import hashlib
import time

from typing import List

from fastapi import APIRouter, Request, Depends, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.db.database import get_db_session
from services.db.models.incident import Incident, IncidentStatus
from services.http.schemas.incident import IncidentListItemResponse

router = APIRouter(prefix="/incidents", tags=["Incidents"])


class SimulateIncidentRequest(BaseModel):
    scenario: str = "oomkill"


SCENARIO_ALERTS = {
    "oomkill": lambda ts: {
        "source": "datadog",
        "metric": "container.memory.usage",
        "threshold": 0.95,
        "current_value": 0.99,
        "pod_name": f"auth-service-7d84b8f58b-{ts % 10000}",
        "namespace": "production",
        "restarts_last_hour": 5,
        "cluster": "k8s-prod-us-east-1",
        "timestamp": ts,
        "message": f"Pod auth-service-7d84b8f58b-{ts % 10000} is using 99% memory and has crashed with OOMKilled (exit code 137) 5 times in the last hour.",
    },
    "crashloop": lambda ts: {
        "source": "prometheus",
        "alertname": "KubePodCrashLooping",
        "severity": "critical",
        "pod_name": f"auth-service-7d84b8f58b-{ts % 10000}",
        "namespace": "production",
        "deployment": "auth-service",
        "restarts_last_hour": 7,
        "cluster": "k8s-prod-us-east-1",
        "timestamp": ts,
        "message": f"Pod auth-service-7d84b8f58b-{ts % 10000} in namespace production is in CrashLoopBackOff.",
    },
    "db_pool": lambda ts: {
        "source": "sentry",
        "service": "auth-service",
        "error_type": "OperationalError: FATAL: sorry, too many clients already",
        "pod_name": f"auth-service-7d84b8f58b-{ts % 10000}",
        "namespace": "production",
        "active_connections": 198,
        "max_connections": 200,
        "timestamp": ts,
        "message": "PostgreSQL connection pool exhausted on auth-service (198/200 active connections).",
    },
    "gateway_504": lambda ts: {
        "source": "grafana",
        "alertname": "HighIngress504GatewayTimeout",
        "service": "api-gateway",
        "pod_name": f"auth-service-7d84b8f58b-{ts % 10000}",
        "namespace": "production",
        "p99_latency_ms": 12400,
        "error_rate_5xx": 0.34,
        "timestamp": ts,
        "message": "Upstream HTTP 504 Gateway Timeout rate exceeded 34% on production ingress.",
    },
}


@router.post(
    "/simulate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a simulated alert scenario for testing the autonomous pipeline",
)
async def simulate_incident(
    payload: SimulateIncidentRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    ts = int(time.time() * 1000)
    builder_fn = SCENARIO_ALERTS.get(payload.scenario, SCENARIO_ALERTS["oomkill"])
    raw_alert = builder_fn(ts)

    fingerprint = hashlib.sha256(
        json.dumps(raw_alert, sort_keys=True).encode()
    ).hexdigest()[:64]

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
        _job_id=f"incident:{incident.id}",
    )

    return {
        "incident_id": str(incident.id),
        "status": incident.status,
    }

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
