from typing import Dict, Any

from services.agent.nodes.trace_step import traced_step
from services.agent.state import AgentState


def severity_router(state: AgentState) -> str:
    if state["severity"] == "P1":
        return "P1"
    elif state["severity"] == "P2":
        return "P2"
    else:
        return "P3"

@traced_step("route_p1")
async def route_p1(state: AgentState) -> Dict[str, Any]:
    return {
        "proposed_action": "P1 CRITICAL: Page on-call engineer immediately. Open war room. All hands."
    }
