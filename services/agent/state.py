from enum import Enum
from typing import TypedDict, Dict, Any, List, Optional

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

    # fetch_logs node
    logs: Dict[str, Any]
    logs_summary: str
    # Only consulted when runbooks exist in the DB:
    runbooks_available: bool
    runbooks_needed: bool

    # refer_runbooks node (only runs when runbooks_needed is True)
    runbooks_summary: str

    # recommended_steps node (final)
    recommended_steps: Optional[List[str]]
