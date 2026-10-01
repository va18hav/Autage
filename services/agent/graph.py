from langgraph.graph import StateGraph, START, END
from services.agent.state import AgentState
from services.agent.nodes.triage import process_alert
from services.agent.nodes.severity_router import severity_router, route_p1, route_p2, route_p3
from services.agent.nodes.context_gathering import gather_context

# --- Graph Definition ---
builder = StateGraph(AgentState)

# 1. Register nodes
builder.add_node("process_alert", process_alert)
builder.add_node("route_p1", route_p1)
builder.add_node("route_p2", route_p2)
builder.add_node("route_p3", route_p3)
builder.add_node("gather_context", gather_context)

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

# 4. P1 and P2 → context gathering; P3 → END (low severity, skip deep context)
builder.add_edge("route_p1", "gather_context")
builder.add_edge("route_p2", "gather_context")
builder.add_edge("route_p3", END)

# 5. Context gathering → END (next node goes here later)
builder.add_edge("gather_context", END)




