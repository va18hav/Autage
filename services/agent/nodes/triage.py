from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from services.agent.llm import StepKey, get_llm
from services.agent.nodes.trace_step import traced_step
from services.agent.playbooks import IncidentType
from services.agent.prompts.triage import build_system_prompt
from services.agent.state import AgentState, Severity


class AlertTriage(BaseModel):
    """Facts extracted from the alert. No tools are selected here."""

    incident_title: str = Field(description="Title of the incident")
    description: str = Field(description="Incident description")
    severity: Severity = Field(description="Severity: P1, P2, or P3")
    summary: str = Field(
        description="Concise 2-3 sentence summary of the incident and impact"
    )
    incident_type: IncidentType = Field(
        description=(
            "crash_loop for CrashLoopBackOff/OOMKilled, "
            "bad_deployment for a failed or harmful rollout, "
            "or other when neither applies"
        )
    )
    namespace: Optional[str] = Field(
        default=None,
        description="Kubernetes namespace explicitly present in the alert, else null",
    )
    pod_name: Optional[str] = Field(
        default=None,
        description="Exact pod name explicitly present in the alert, else null",
    )
    deployment_name: Optional[str] = Field(
        default=None,
        description="Exact Deployment name explicitly present in the alert, else null",
    )
    container_name: Optional[str] = Field(
        default=None,
        description="Container name explicitly present in the alert, else null",
    )


def _clean(value: Optional[str]) -> Optional[str]:
    """Normalise optional extracted strings without inventing values."""
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


@traced_step("triage")
async def process_alert(state: AgentState) -> Dict[str, Any]:
    """Extract the incident type and target identifiers from the raw alert."""
    prompt = build_system_prompt(raw_alert=state["raw_alert"])

    llm = get_llm(StepKey.TRIAGE)
    structured_llm = llm.with_structured_output(AlertTriage)
    response: AlertTriage = await structured_llm.ainvoke(prompt)

    return {
        "incident_title": response.incident_title,
        "description": response.description,
        "severity": response.severity,
        "summary": response.summary,
        "incident_type": response.incident_type,
        "namespace": _clean(response.namespace),
        "pod_name": _clean(response.pod_name),
        "deployment_name": _clean(response.deployment_name),
        "container_name": _clean(response.container_name),
    }
