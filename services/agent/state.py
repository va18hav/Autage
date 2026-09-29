from pydantic import BaseModel, Field
from typing import TypedDict, Dict, Any

class AlertTriage(BaseModel):
    severity: str = Field(description="Severity: P1, P2, or P3")
    summary: str = Field(description="Concise 2-3 sentence summary of incident and impact")

class AgentState(TypedDict):
    incident_title: str
    incident_id: str
    description: str
    raw_alert: Dict[str, Any]

    severity: str
    issue_type: str

    summary: str