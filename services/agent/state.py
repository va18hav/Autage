from enum import Enum
from pydantic import BaseModel, Field
from typing import TypedDict, Dict, Any, Optional

class Severity(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"

class AgentState(TypedDict):
    incident_title: str
    incident_id: str
    description: str
    raw_alert: Dict[str, Any]
    severity: Severity
    issue_type: str
    summary: str
    proposed_action: str
    context: Dict[str, Any]
    context_summary: str
    context_error: Optional[str]

