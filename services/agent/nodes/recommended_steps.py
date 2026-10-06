from pydantic import BaseModel, Field
from typing import List

from services.agent.llm import StepKey, get_llm

from services.agent.state import AgentState
from services.agent.prompts.fetch_logs import build_recommended_steps_prompt
from services.agent.nodes.trace_step import traced_step


class RecommendedSteps(BaseModel):
    """Concrete, ordered remediation steps handed to the on-call engineer."""
    reasoning: str = Field(description="One-line rationale for the plan")
    recommended_steps: List[str] = Field(description="Ordered list of concrete remediation steps")


@traced_step("recommended_steps")
async def recommended_steps(state: AgentState) -> dict:
    """
    Final node — sees the entire agent state (title, triage summary, logs,
    logs_summary, runbooks_summary when present) and produces the concrete
    recommended steps.
    """
    prompt = build_recommended_steps_prompt(
        incident_title=state["incident_title"],
        severity=state["severity"],
        summary=state["summary"],
        logs_summary=state.get("logs_summary") or "No kubectl logs were fetched for this incident.",
        runbooks_summary=state.get("runbooks_summary") or "",
    )

    llm = get_llm(StepKey.RECOMMENDATIONS)
    structured = llm.with_structured_output(RecommendedSteps)
    response: RecommendedSteps = await structured.ainvoke(prompt)

    return {"recommended_steps": response.recommended_steps}
