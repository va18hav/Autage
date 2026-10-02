import asyncio
from arq.connections import RedisSettings

from services.config import settings
from services.db.database import async_session_factory
from services.db.models.incident import Incident
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
    
    # Run the graph in a threadpool so it doesn't block the ARQ event loop
    # (since our graph nodes are currently synchronous)
    await agent_graph.ainvoke(initial_state)
    print(f"Agent finished processing incident {incident_id}")


class WorkerSettings:
    functions = [run_agent_task]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_jobs = 10