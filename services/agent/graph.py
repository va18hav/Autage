from langgraph.graph import StateGraph
from services.agent.state import AgentState
from services.agent.nodes.triage import process_alert
from services.agent.nodes.severity_router import route_p1

# --- Graph Definition ---
builder = StateGraph(AgentState)

# 1. Register nodes
builder.add_node("process_alert", process_alert)
builder.add_node("route_p1", route_p1)
