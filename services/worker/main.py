import os
import json
from arq.connections import RedisSettings
from sqlalchemy import update

from services.agent.state import AgentState
from services.agent.llm import (
    LlmConfigError,
    LlmResolver,
    reset_resolver,
    set_resolver,
)
from services.agent.llm.resolver import friendly_error
from services.config import settings

# Keep the mock tooling switch working without real cluster access.
if settings.MOCK_KUBECTL:
    os.environ["MOCK_KUBECTL"] = "true"

from services.db.database import async_session_factory
from services.db.models.incident import Incident, IncidentStatus
from services.agent.graph import builder

# Compile the graph
agent_graph = builder.compile()

async def run_agent_task(ctx, incident_id: str):
    """
    Dumb worker: Fetches the incident and kicks off the agent.
    The agent nodes themselves will handle writing steps to the DB.
    """
    async with async_session_factory() as db:
        incident = await db.get(Incident, incident_id)
        if not incident:
            print(f"Incident {incident_id} not found!")
            return

        # We pass both the raw alert and the incident_id into the graph state
        # so the nodes know which incident to attach their DB steps to.
        initial_state = {
            "incident_id": str(incident.id),
            "raw_alert": incident.raw_alert
        }

        #Mark as triaging
        await db.execute(
            update(Incident)
            .where(Incident.id == incident_id)
            .values(status=IncidentStatus.TRIAGING)
        )
        await db.commit()

    channel = f"incident:{incident_id}:events"

    await ctx["redis"].publish(
        channel,
        json.dumps({"type": "status", "status": "TRIAGING"}),
    )

    final_state = {}

    # One resolver per run: step configs + credentials read from the DB once,
    # then made available to every node via get_llm().
    resolver_token = None

    try:
        resolver = await LlmResolver.load()
        resolver_token = set_resolver(resolver)

        # Run the graph in a threadpool so it doesn't block the ARQ event loop
        # (since our graph nodes are currently synchronous)
        async for chunk in agent_graph.astream(initial_state, stream_mode="updates"):

            for node_name, node_output in chunk.items():
                final_state.update(node_output)

                await ctx["redis"].publish(
                    channel,
                    json.dumps(
                        {
                            "type": "step_complete",
                            "node": node_name,
                            "data": node_output,
                        },
                        default=str,
                    )
                )

        # Final recommended steps come from the dedicated node (list of steps);
        # published and persisted so the dashboard renders the numbered list.
        recommended = final_state.get("recommended_steps")

        async with async_session_factory() as db:
            await db.execute(
                update(Incident)
                .where(Incident.id == incident_id)
                .values(
                    title=final_state.get("incident_title", incident.title),
                    status=IncidentStatus.COMPLETED,
                    recommended_steps=recommended,
                )
            )
            await db.commit()

        await ctx["redis"].publish(
            channel,
            json.dumps({
                "type": "incident_complete",
                "status": "COMPLETED",
                "title": final_state.get("incident_title"),
                "recommended_steps": recommended,
            }, default=str)
        )

    except LlmConfigError as exc:
        # Config problem (missing/unknown provider credential) — message is
        # user-fixable, surface it verbatim to the dashboard.
        print(f"Config error processing incident {incident_id}: {exc}")
        await _fail_incident(ctx, channel, incident_id, error=str(exc))
        raise

    except Exception as exc:
        error = friendly_error(exc)
        print(f"Error processing incident {incident_id}: {error}")
        await _fail_incident(ctx, channel, incident_id, error=error)
        raise

    finally:
        if resolver_token is not None:
            reset_resolver(resolver_token)


async def _fail_incident(ctx, channel: str, incident_id: str, error: str) -> None:
    async with async_session_factory() as db:
        await db.execute(
            update(Incident)
            .where(Incident.id == incident_id)
            .values(status=IncidentStatus.FAILED)
        )
        await db.commit()

    await ctx["redis"].publish(
        channel,
        json.dumps({
            "type": "incident_failed",
            "status": "FAILED",
            "error": error
        })
    )



class WorkerSettings:
    functions = [run_agent_task]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_jobs = 10