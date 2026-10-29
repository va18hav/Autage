from typing import Any, Dict, List

from pydantic import BaseModel, Field

from services.agent.llm import StepKey, get_llm
from services.agent.nodes.trace_step import traced_step
from services.agent.playbooks import IncidentType, get_playbook
from services.agent.prompts.diagnosis import build_diagnosis_prompt
from services.agent.state import AgentState, Confidence, Diagnosis


class DiagnosisOutput(BaseModel):
    """Schema returned by the diagnosis model."""

    what_happened: str = Field(description="Short factual description of the incident")
    likely_cause: str = Field(
        description="Most likely cause, or 'Unclear' when evidence is insufficient"
    )
    confidence: Confidence = Field(description="low, medium, or high")
    what_i_found: str = Field(
        description="Strongest specific observations from the evidence"
    )
    missing_information: List[str] = Field(
        description="Evidence that failed, was unavailable, or is still needed"
    )
    recommended_steps: List[str] = Field(
        description="Ordered, actionable next steps for the operator"
    )


def _clean_steps(steps: List[str]) -> List[str]:
    cleaned = [step.strip() for step in steps if isinstance(step, str) and step.strip()]
    return cleaned[:6]


def _unsupported_diagnosis(state: AgentState) -> Diagnosis:
    missing = list(state.get("missing_evidence") or [])
    return {
        "what_happened": state.get("summary") or "An alert was received.",
        "likely_cause": (
            "Unclear. Autage does not yet have a specialised playbook for this "
            "incident type."
        ),
        "confidence": Confidence.LOW,
        "what_i_found": "Only the alert data was available for this incident.",
        "missing_information": missing,
        "recommended_steps": [
            "Review the alert and confirm the affected service and namespace.",
            "Check recent deployments and Kubernetes events for the affected workload.",
            "Inspect pod status and logs for the affected service.",
            "Use the team runbook or escalate to the service owner if the cause remains unclear.",
        ],
    }


def _normalise_response(
    response: DiagnosisOutput,
    state: AgentState,
) -> Diagnosis:
    steps = _clean_steps(response.recommended_steps)
    if not steps:
        raise ValueError("The diagnosis model returned no recommended steps")

    missing = [item.strip() for item in response.missing_information if item.strip()]
    for item in state.get("missing_evidence") or []:
        if item not in missing:
            missing.append(item)

    confidence = response.confidence
    evidence = state.get("evidence") or []
    has_successful_evidence = any(
        item.get("ok") and (item.get("output") or "").strip() for item in evidence
    )
    if not has_successful_evidence:
        confidence = Confidence.LOW
    elif missing and confidence == Confidence.HIGH:
        confidence = Confidence.MEDIUM

    likely_cause = response.likely_cause.strip()
    if not has_successful_evidence and not likely_cause:
        likely_cause = "Unclear. No Kubernetes evidence was collected."

    return {
        "what_happened": response.what_happened.strip(),
        "likely_cause": likely_cause or "Unclear",
        "confidence": confidence,
        "what_i_found": response.what_i_found.strip(),
        "missing_information": missing,
        "recommended_steps": steps,
    }


@traced_step("diagnose")
async def diagnose(state: AgentState) -> Dict[str, Any]:
    """Turn the collected evidence into one structured, conservative diagnosis."""
    incident_type = state.get("incident_type") or IncidentType.OTHER
    if get_playbook(incident_type) is None:
        return {"diagnosis": _unsupported_diagnosis(state)}

    prompt = build_diagnosis_prompt(
        incident_title=state["incident_title"],
        incident_type=getattr(incident_type, "value", str(incident_type)),
        summary=state["summary"],
        namespace=state.get("namespace"),
        pod_name=state.get("pod_name"),
        deployment_name=state.get("deployment_name"),
        evidence=state.get("evidence") or [],
        missing_evidence=state.get("missing_evidence") or [],
        runbooks_summary=state.get("runbooks_summary") or "",
    )

    llm = get_llm(StepKey.DIAGNOSE)
    structured = llm.with_structured_output(DiagnosisOutput)

    response = None
    for _attempt in range(2):
        response = await structured.ainvoke(prompt)
        if response is not None and _clean_steps(response.recommended_steps):
            break
        prompt += (
            "\n\n## Reminder\nThe previous response was rejected because it had no "
            "usable recommended_steps. Return the structured diagnosis with 3 to 6 "
            "non-empty, ordered steps."
        )

    if response is None:
        raise RuntimeError("The diagnosis model did not return a response")
    if not _clean_steps(response.recommended_steps):
        raise RuntimeError(
            "The diagnosis model did not return any usable recommended steps "
            "after a retry."
        )

    return {"diagnosis": _normalise_response(response, state)}
