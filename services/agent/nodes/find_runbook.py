from typing import Any, Dict, List

from services.agent.nodes.trace_step import traced_step
from services.agent.playbooks import IncidentType, get_playbook
from services.agent.state import AgentState
from services.agent.tools.runbooks import find_runbooks_for_incident


def _format_matches(matches: List[dict]) -> str:
    sections: List[str] = []

    for match in matches:
        service = match.get("service") or "unspecified service"
        sections.append(
            f"## Runbook: {match['title']} (service: {service})"
        )
        if match.get("description"):
            sections.append(str(match["description"]))

        for section in match.get("sections") or []:
            heading = section.get("heading") or "Untitled section"
            content = section.get("content") or ""
            sections.append(f"### {heading}\n{content}")

    return "\n\n".join(sections).strip()


@traced_step("find_runbook")
async def find_runbook(state: AgentState) -> Dict[str, Any]:
    """Find bounded runbook sections that match the incident's service and type."""
    incident_type = state.get("incident_type") or IncidentType.OTHER
    if get_playbook(incident_type) is None:
        return {"runbooks_summary": ""}

    service = state.get("deployment_name")

    try:
        matches = await find_runbooks_for_incident(
            service=service,
            incident_type=getattr(incident_type, "value", str(incident_type)),
        )
    except Exception as exc:
        message = f"Runbook lookup failed: {exc}"
        missing = list(state.get("missing_evidence") or [])
        if message not in missing:
            missing.append(message)
        return {
            "runbooks_summary": "",
            "missing_evidence": missing,
        }

    return {"runbooks_summary": _format_matches(matches)}
