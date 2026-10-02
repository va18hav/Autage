from services.db.models.incident import StepStatus
from services.db.models.incident import IncidentStep
from services.db.database import async_session_factory
from typing import Dict, Any
from sqlalchemy import update
from enum import Enum
from pydantic import BaseModel, Field
from services.agent.state import AgentState
from services.agent.prompts.triage import build_system_prompt
from langchain_google_genai import ChatGoogleGenerativeAI

class Severity(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"

class AlertTriage(BaseModel):
    incident_title: str = Field(description="Title of the incident")
    description: str = Field(description="Incident description")
    severity: Severity = Field(description="Severity: P1, P2, or P3")
    summary: str = Field(description="Concise 2-3 sentence summary of incident and impact")


async def process_alert(state: AgentState) -> Dict[str, Any]:
    """This node processes the raw alert, classifies severity, and summarizes it."""
    # 1. Insert the initial step as RUNNING and capture its ID
    async with async_session_factory() as db:
        step = IncidentStep(
            incident_id=state["incident_id"],
            step_name="triage",
            status=StepStatus.RUNNING,
        )
        db.add(step)
        await db.commit()
        await db.refresh(step)
        step_id = step.id

    try:
        prompt = build_system_prompt(raw_alert=state["raw_alert"])

        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
        structured_llm = llm.with_structured_output(AlertTriage)
        response: AlertTriage = await structured_llm.ainvoke(prompt)

        async with async_session_factory() as db:
            await db.execute(
                update(IncidentStep)
                .where(IncidentStep.id == step_id)
                .values(status=StepStatus.COMPLETED)
            )
            await db.commit()

        return {
            "incident_title": response.incident_title,
            "description": response.description,
            "severity": response.severity,
            "summary": response.summary,
        }

    except Exception as e:

        async with async_session_factory() as db:
            await db.execute(
                update(IncidentStep)
                .where(IncidentStep.id == step_id)
                .values(status=StepStatus.FAILED)
            )
            await db.commit()
        raise e