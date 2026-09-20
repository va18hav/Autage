from langgraph.graph import StateGraph
from services.agent.state import AgentState
from services.agent.nodes.triage import process_alert

# --- Graph Definition ---
builder = StateGraph(AgentState)

# 1. Register nodes
builder.add_node("process_alert", process_alert)
