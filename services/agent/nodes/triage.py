from typing import Dict, Any
from enum import Enum
from pydantic import BaseModel, Field
from services.agent.state import AgentState
from services.agent.prompts.triage import build_system_prompt
from services.agent.nodes.trace_step import traced_step
from services.agent.llm import StepKey, get_llm
from services.agent.nodes.trace_step import traced_step

class Severity(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"

class AlertTriage(BaseModel):
    incident_title: str = Field(description="Title of the incident")
    description: str = Field(description="Incident description")
    severity: Severity = Field(description="Severity: P1, P2, or P3")
    summary: str = Field(description="Concise 2-3 sentence summary of incident and impact")


@traced_step("triage")
async def process_alert(state: AgentState) -> Dict[str, Any]:
    """This node processes the raw alert, classifies severity, and summarizes it."""
    prompt = build_system_prompt(raw_alert=state["raw_alert"])

    llm = get_llm(StepKey.TRIAGE)
    structured_llm = llm.with_structured_output(AlertTriage)
    response: AlertTriage = await structured_llm.ainvoke(prompt)

    return {
        "incident_title": response.incident_title,
        "description": response.description,
        "severity": response.severity,
        "summary": response.summary,
    }
