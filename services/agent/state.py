from enum import Enum
from typing import Any, Dict, List, Optional, TypedDict

from services.agent.playbooks import IncidentType


class Severity(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class Confidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EvidenceRecord(TypedDict):
    """One read-only observation collected by a playbook."""

    tool: str
    scope: str
    target: str
    ok: bool
    output: str
    error: Optional[str]
    truncated: bool


class Diagnosis(TypedDict):
    """Structured result shown to the operator."""

    what_happened: str
    likely_cause: str
    confidence: Confidence
    what_i_found: str
    missing_information: List[str]
    recommended_steps: List[str]


class AgentState(TypedDict):
    # Incident identity and input
    incident_id: str
    raw_alert: Dict[str, Any]

    # Triage output
    incident_title: str
    description: str
    severity: Severity
    summary: str
    incident_type: IncidentType

    # Resolved target — populated from alert/evidence, not invented by the model
    namespace: Optional[str]
    pod_name: Optional[str]
    deployment_name: Optional[str]
    container_name: Optional[str]

    # Fixed-playbook evidence
    evidence: List[EvidenceRecord]
    missing_evidence: List[str]

    # Runbook lookup
    runbooks_summary: str

    # Final structured result
    diagnosis: Optional[Diagnosis]
