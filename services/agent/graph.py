from langgraph.graph import END, START, StateGraph

from services.agent.nodes.diagnose import diagnose
from services.agent.nodes.investigate import investigate
from services.agent.nodes.search_runbook import search_runbook
from services.agent.nodes.triage import process_alert
from services.agent.state import AgentState

# Fixed read-only pipeline. Runbook context is loaded before the investigation
# so it can guide which evidence the model collects.
builder = StateGraph(AgentState)

builder.add_node("triage", process_alert)
builder.add_node("search_runbook", search_runbook)
builder.add_node("investigate", investigate)
builder.add_node("diagnose", diagnose)

builder.add_edge(START, "triage")
builder.add_edge("triage", "search_runbook")
builder.add_edge("search_runbook", "investigate")
builder.add_edge("investigate", "diagnose")
builder.add_edge("diagnose", END)
