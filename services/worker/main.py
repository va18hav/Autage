import os
import json
import asyncio
from arq.connections import RedisSettings
from sqlalchemy import update

from services.agent.state import AgentState
from services.config import settings

# Ensure LangChain and Google GenAI have the API key in environment
if settings.GOOGLE_API_KEY:
    os.environ["GOOGLE_API_KEY"] = settings.GOOGLE_API_KEY
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
    
    # Run the graph in a threadpool so it doesn't block the ARQ event loop
    # (since our graph nodes are currently synchronous)
    try:
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

        # Recommended steps come from the LLM's context summary, not the raw
        # routing action (proposed_action) produced by the router nodes.
        context_summary = final_state.get("context_summary") or {}
        recommended = context_summary.get("recommended_next_steps")

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

    except Exception as exc:
        print(f"Error processing incident {incident_id}: {exc}")
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
                "error": str(exc)
            })
        )
        raise exc



class WorkerSettings:
    functions = [run_agent_task]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_jobs = 10