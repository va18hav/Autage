
from services.agent.state import AgentState


def severity_router(state: AgentState) -> str:
    if state["severity"] == "P1":
        return "P1"
    elif state["severity"] == "P2":
        return "P2"
    else:
        return "P3"
