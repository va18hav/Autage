import sys
from pathlib import Path

# Add project root to sys.path so it works directly from CLI
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import uuid

from services.db.database import async_session_factory
from services.db.models.incident import Incident, IncidentStatus, IncidentStep, StepStatus


async def seed():
    print("--> Seeding database with mock incidents and steps...")

    async with async_session_factory() as db:
        # ── Incident 1: Critical OOMKill Crash (Completed) ────────────────────
        inc1_id = uuid.uuid4()
        inc1 = Incident(
            id=inc1_id,
            title="Auth-Service CrashLoopBackOff due to Memory Leak",
            status=IncidentStatus.COMPLETED,
            fingerprint="seed-fp-auth-oomkill-01",
            raw_alert={
                "source": "datadog",
                "metric": "container.memory.usage",
                "threshold": 0.95,
                "current_value": 0.99,
                "pod_name": "auth-service-7d84b8f58b-xyz",
                "namespace": "production",
                "restarts_last_hour": 4,
                "cluster": "k8s-prod-us-east-1",
            },
            recommended_steps={
                "action": "P1 CRITICAL: Page on-call engineer immediately. Increase container memory limit from 512Mi to 1Gi and inspect auth token cache size.",
                "root_cause": "OOMKilled exit code 137 in auth-service container due to unbounded session cache.",
            },
        )
        db.add(inc1)

        step1_1 = IncidentStep(
            id=uuid.uuid4(),
            incident_id=inc1_id,
            step_name="triage",
            status=StepStatus.COMPLETED,
            input_data={"source": "datadog", "metric": "container.memory.usage"},
            output_data={
                "incident_title": "Auth-Service CrashLoopBackOff due to Memory Leak",
                "severity": "P1",
                "summary": "Production auth-service pods are repeatedly OOMKilling with memory usage exceeding 99%.",
            },
        )
        step1_2 = IncidentStep(
            id=uuid.uuid4(),
            incident_id=inc1_id,
            step_name="context_gathering",
            status=StepStatus.COMPLETED,
            input_data={"tools_executed": ["get_pod_logs", "describe_pod", "get_events"]},
            output_data={
                "affected_pods": ["auth-service-7d84b8f58b-xyz"],
                "root_cause_hypothesis": "Pod terminated with OOMKilled (Exit Code 137). High memory consumption in JVM heap.",
                "key_signals": [
                    "Last state terminated: OOMKilled",
                    "Restart count: 4 within 45 minutes",
                    "Node memory pressure normal; issue isolated to auth-service cgroup",
                ],
                "recommended_next_steps": [
                    "Scale deployment memory limit from 512Mi to 1Gi",
                    "Inspect Redis session offloader to ensure tokens are not retained in-memory",
                ],
            },
        )
        db.add(step1_1)
        db.add(step1_2)

        # ── Incident 2: Payment Gateway 5xx Elevated Errors (Completed) ───────
        inc2_id = uuid.uuid4()
        inc2 = Incident(
            id=inc2_id,
            title="Payment-Gateway 5xx Error Rate Exceeded 5%",
            status=IncidentStatus.COMPLETED,
            fingerprint="seed-fp-payment-5xx-02",
            raw_alert={
                "source": "prometheus",
                "alertname": "High5xxErrorRate",
                "service": "payment-gateway",
                "namespace": "payments",
                "error_rate": "8.4%",
                "threshold": "5.0%",
            },
            recommended_steps={
                "action": "P2: Rollback deployment payment-gateway to revision 41 and notify payments on-call.",
                "root_cause": "Upstream Stripe webhook timeout introduced in release v2.4.1.",
            },
        )
        db.add(inc2)

        step2_1 = IncidentStep(
            id=uuid.uuid4(),
            incident_id=inc2_id,
            step_name="triage",
            status=StepStatus.COMPLETED,
            output_data={
                "incident_title": "Payment-Gateway 5xx Error Rate Exceeded 5%",
                "severity": "P2",
                "summary": "Elevated 5xx error rate detected on payment checkout flows following v2.4.1 deployment.",
            },
        )
        step2_2 = IncidentStep(
            id=uuid.uuid4(),
            incident_id=inc2_id,
            step_name="context_gathering",
            status=StepStatus.COMPLETED,
            output_data={
                "affected_pods": ["payment-gw-6f8d7b-1", "payment-gw-6f8d7b-2"],
                "root_cause_hypothesis": "Connection pool exhaustion connecting to downstream payment processing provider.",
                "key_signals": [
                    "HTTP 504 Gateway Timeout accounts for 85% of errors",
                    "Database latency remains low (<5ms)",
                ],
            },
        )
        db.add(step2_1)
        db.add(step2_2)

        # ── Incident 3: Kafka Consumer Lag (Triaging / In Progress) ───────────
        inc3_id = uuid.uuid4()
        inc3 = Incident(
            id=inc3_id,
            title="Kafka Consumer Lag Exceeded on order-events-prod",
            status=IncidentStatus.TRIAGING,
            fingerprint="seed-fp-kafka-lag-03",
            raw_alert={
                "source": "cloudwatch",
                "topic": "order-events-prod",
                "consumer_group": "order-fulfillment-worker",
                "lag_records": 48200,
                "threshold": 10000,
            },
            recommended_steps=None,
        )
        db.add(inc3)

        step3_1 = IncidentStep(
            id=uuid.uuid4(),
            incident_id=inc3_id,
            step_name="triage",
            status=StepStatus.COMPLETED,
            output_data={
                "incident_title": "Kafka Consumer Lag Exceeded on order-events-prod",
                "severity": "P2",
                "summary": "Order fulfillment consumers are lagging by ~48k messages. Pipeline delayed by ~18 minutes.",
            },
        )
        step3_2 = IncidentStep(
            id=uuid.uuid4(),
            incident_id=inc3_id,
            step_name="context_gathering",
            status=StepStatus.RUNNING,
            output_data=None,
        )
        db.add(step3_1)
        db.add(step3_2)

        await db.commit()

    print("[OK] Successfully seeded 3 mock incidents with steps into PostgreSQL!")


if __name__ == "__main__":
    asyncio.run(seed())
