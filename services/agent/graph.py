from langgraph.graph import StateGraph
from services.agent.state import AgentState
from services.agent.nodes.triage import process_alert
from services.agent.nodes.severity_router import route_p1, route_p2, route_p3
from services.agent.nodes.fetch_logs import fetch_logs
from services.agent.nodes.refer_runbooks import refer_runbooks
from services.agent.nodes.recommended_steps import recommended_steps

# --- Graph Definition ---
builder = StateGraph(AgentState)

# 1. Register nodes
builder.add_node("process_alert", process_alert)
builder.add_node("route_p1", route_p1)
builder.add_node("route_p2", route_p2)
builder.add_node("route_p3", route_p3)
builder.add_node("fetch_logs", fetch_logs)
builder.add_node("refer_runbooks", refer_runbooks)
builder.add_node("recommended_steps", recommended_steps)
