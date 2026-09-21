from langgraph.graph import StateGraph, START
from services.agent.state import AgentState
from services.agent.nodes.triage import process_alert
from services.agent.nodes.severity_router import severity_router, route_p1, route_p2, route_p3
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

# 2. Entry point
builder.add_edge(START, "process_alert")

# 3. Triage → severity router
builder.add_conditional_edges(
    "process_alert",
    severity_router,
    {
        "P1": "route_p1",
        "P2": "route_p2",
        "P3": "route_p3"
    }
)

# 4. P1/P2 → fetch logs; P3 (low severity) skips logs and runbooks
builder.add_edge("route_p1", "fetch_logs")
builder.add_edge("route_p2", "fetch_logs")
