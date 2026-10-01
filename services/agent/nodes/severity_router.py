from services.agent.state import AgentState

def severity_router(state: AgentState) -> AgentState:
    if state["severity"] == "P1":
        return "P1"
    elif state["severity"] == "P2":
        return "P2"
    else:
        return "P3"

def route_p1(state: AgentState) -> dict:
    return{
        "proposed_action": "P1 CRITICAL: Page on-call engineer immediately. Open war room. All hands."
    }

def route_p2(state: AgentState) -> dict:
    return{
        "proposed_action": "P2 Less critical"
    }

def route_p3(state: AgentState) -> dict:
    return{
        "proposed_action": "P3: Create a ticket"
    }

