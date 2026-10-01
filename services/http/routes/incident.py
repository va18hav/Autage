

from fastapi import APIRouter
from pydantic import BaseModel


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
