from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from services.agent.state import AgentState
from services.agent.nodes.triage import process_alert

load_dotenv()

# --- Graph Definition ---
builder = StateGraph(AgentState)

# 1. Add the node
builder.add_node("process_alert", process_alert)

# 2. Add edges (Start -> process_alert -> End)
builder.add_edge(START, "process_alert")
builder.add_edge("process_alert", END)

