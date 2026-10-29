from langgraph.graph import END, START, StateGraph

from services.agent.nodes.collect_evidence import collect_evidence
from services.agent.nodes.diagnose import diagnose
from services.agent.nodes.find_runbook import find_runbook
from services.agent.nodes.triage import process_alert
from services.agent.state import AgentState

# Fixed read-only pipeline. The incident type selects a playbook inside
# collect_evidence; it does not change the graph topology.
builder = StateGraph(AgentState)

builder.add_node("triage", process_alert)
builder.add_node("collect_evidence", collect_evidence)
builder.add_node("find_runbook", find_runbook)
builder.add_node("diagnose", diagnose)

builder.add_edge(START, "triage")
builder.add_edge("triage", "collect_evidence")
builder.add_edge("collect_evidence", "find_runbook")
builder.add_edge("find_runbook", "diagnose")
builder.add_edge("diagnose", END)
