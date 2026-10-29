import asyncio
import json
import logging
import signal
from typing import Any
from uuid import UUID

import redis.asyncio as redis
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from services.agent.graph import builder
from services.agent.llm import (
    LlmConfigError,
    LlmResolver,
    reset_resolver,
    set_resolver,
)
from services.agent.llm.resolver import friendly_error
from services.agent.state import AgentState
from services.config import settings
from services.db.database import async_session_factory
from services.db.models.incident import Incident, IncidentStatus
from services.worker import queue

logger = logging.getLogger("autage.worker")

# Kept as a module-level default so tests can inject a graph. The real worker
# replaces it with a checkpoint-enabled graph in main().
agent_graph = builder.compile()


def _has_checkpoint(snapshot: Any) -> bool:
    return bool(
        getattr(snapshot, "created_at", None)
        or getattr(snapshot, "values", None)
        or getattr(snapshot, "next", None)
    )


async def _publish(redis_client: Any, channel: str, payload: dict) -> None:
    await redis_client.publish(channel, json.dumps(payload, default=str))


async def _handle_failure(
    redis_client: Any,
    incident_id: UUID,
    error: str,
    *,
    terminal: bool = False,
) -> None:
    channel = f"incident:{incident_id}:events"

    async with async_session_factory() as db:
        incident = await db.get(Incident, incident_id)
        if incident is None or incident.status in (
            IncidentStatus.COMPLETED,
            IncidentStatus.FAILED,
        ):
            return

        attempts = incident.attempts or 0
        if terminal or attempts >= settings.WORKER_MAX_ATTEMPTS:
            await queue.mark_incident_failed(db, incident_id, error)
            await _publish(
                redis_client,
                channel,
                {
                    "type": "incident_failed",
                    "status": "FAILED",
                    "error": error,
                },
            )
            return

        delay = settings.WORKER_RETRY_DELAY_SECONDS * max(1, attempts)
        await queue.schedule_incident_retry(db, incident_id, error, delay)
        await _publish(
            redis_client,
            channel,
            {
                "type": "status",
                "status": "PENDING",
                "error": error,
            },
        )


async def run_agent_task(redis_client: Any, graph: Any, incident_id: str) -> None:
    """Run or resume one incident graph and persist its terminal state."""
    async with async_session_factory() as db:
        incident = await db.get(Incident, incident_id)
        if incident is None:
            logger.warning("Incident %s not found", incident_id)
            return

        await queue.mark_interrupted_steps(db, incident.id)
        initial_state: AgentState = {
            "incident_id": str(incident.id),
            "raw_alert": incident.raw_alert,
        }
        config = {"configurable": {"thread_id": str(incident.id)}}
        snapshot = await graph.aget_state(config)
        has_checkpoint = _has_checkpoint(snapshot)

    channel = f"incident:{incident_id}:events"
    await _publish(redis_client, channel, {"type": "status", "status": "TRIAGING"})

    resolver_token = None
    try:
        resolver = await LlmResolver.load()
        resolver_token = set_resolver(resolver)

        snapshot_values = dict(getattr(snapshot, "values", None) or {})
        next_nodes = tuple(getattr(snapshot, "next", None) or ())

        if not has_checkpoint or next_nodes:
            # None tells LangGraph to resume from the latest checkpoint. It is
            # ignored for a fresh run, where initial_state supplies the input.
            stream_input = None if has_checkpoint else initial_state
            async for chunk in graph.astream(
                stream_input,
                config=config,
                stream_mode="updates",
                durability="sync",
            ):
                for node_name, node_output in chunk.items():
                    snapshot_values.update(node_output)
                    await _publish(
                        redis_client,
                        channel,
                        {
                            "type": "step_complete",
                            "node": node_name,
                            "data": node_output,
                        },
                    )

            snapshot = await graph.aget_state(config)
            snapshot_values = dict(getattr(snapshot, "values", None) or {})

        diagnosis = snapshot_values.get("diagnosis")
        if not isinstance(diagnosis, dict):
            raise RuntimeError("The agent completed without producing a diagnosis")

        recommended = diagnosis.get("recommended_steps") or []
        incident_type = snapshot_values.get("incident_type")
        incident_type_value = getattr(incident_type, "value", incident_type)

        async with async_session_factory() as db:
            await queue.mark_incident_completed(
                db,
                UUID(incident_id),
                title=snapshot_values.get("incident_title", "Incident resolved"),
                incident_type=incident_type_value,
                analysis=diagnosis,
                recommended_steps=recommended,
            )

        await _publish(
            redis_client,
            channel,
            {
                "type": "incident_complete",
                "status": "COMPLETED",
                "title": snapshot_values.get("incident_title"),
                "incident_type": incident_type_value,
                "analysis": diagnosis,
                "recommended_steps": recommended,
            },
        )

    except LlmConfigError as exc:
        logger.error("Config error processing incident %s: %s", incident_id, exc)
        await _handle_failure(redis_client, UUID(incident_id), str(exc), terminal=True)

    except asyncio.CancelledError:
        # The checkpoint is already durable; the next claim resumes it.
        raise

    except Exception as exc:
        error = friendly_error(exc)
        logger.exception("Error processing incident %s: %s", incident_id, error)
        await _handle_failure(redis_client, UUID(incident_id), error)

    finally:
        if resolver_token is not None:
            reset_resolver(resolver_token)


async def worker_loop(
    redis_client: Any,
    graph: Any,
    stop_event: asyncio.Event,
) -> None:
    while not stop_event.is_set():
        async with async_session_factory() as db:
            incident = await queue.claim_next_incident(
                db,
                settings.WORKER_MAX_ATTEMPTS,
            )

        if incident is None:
            await asyncio.sleep(settings.WORKER_POLL_SECONDS)
            continue

        try:
            await asyncio.wait_for(
                run_agent_task(redis_client, graph, str(incident.id)),
                timeout=settings.WORKER_JOB_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            await _handle_failure(
                redis_client,
                incident.id,
                "Worker timed out before the agent completed.",
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Unhandled worker error for incident %s", incident.id)
            await _handle_failure(
                redis_client,
                incident.id,
                friendly_error(exc),
            )


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    async with AsyncPostgresSaver.from_conn_string(
        settings.psycopg_database_url
    ) as checkpointer:
        await checkpointer.setup()
        graph = builder.compile(checkpointer=checkpointer)
        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=False)

        try:
            async with async_session_factory() as db:
                released = await queue.release_interrupted_leases(db)
                failed = await queue.fail_exhausted_incidents(
                    db,
                    settings.WORKER_MAX_ATTEMPTS,
                )
            if released:
                logger.info("Released %s interrupted incident lease(s)", released)
            if failed:
                logger.warning("Marked %s exhausted incident(s) failed", len(failed))

            logger.info("Worker started; polling Postgres for incidents")
            await worker_loop(redis_client, graph, stop_event)
        finally:
            await redis_client.aclose()
            logger.info("Worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
