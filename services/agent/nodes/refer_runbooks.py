from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI

from services.agent.state import AgentState
from services.agent.prompts.fetch_logs import build_runbook_selection_prompt
from services.agent.nodes.trace_step import traced_step
from services.agent.tools.runbooks import list_runbooks, get_runbook_sections


class SectionRequest(BaseModel):
    """A runbook section the LLM wants the content of."""
    runbook_title: str          = Field(description="Title of the runbook containing the section")
    section_order_index: int    = Field(description="order_index of the section within that runbook")


class SectionsSelection(BaseModel):
    """Which runbook sections to pull the full content of."""
    reasoning: str              = Field(description="Brief reasoning for why these sections were chosen")
    sections: List[SectionRequest] = Field(description="Sections to load; empty list if none are relevant")


@traced_step("refer_runbooks")
async def refer_runbooks(state: AgentState) -> Dict[str, Any]:
    """
    Refer runbooks node (conditional: only runs when runbooks are present and
    fetch_logs flagged them as needed).

    Tool 1 — list_runbooks() returns runbook titles + section headings only.
    LLM    — picks the specific sections likely to contain the remediation.
    Tool 2 — get_runbook_sections() loads the full content of those sections.
    LLM    — summarizes the chosen procedures into a plain-text summary.
    """
    llm = ChatGoogleGenerativeAI(model="gemini-3.7-flash", temperature=0)

    # ── Tool 1: inventory (titles + section headings only) ───────────────
    inventory: List[Dict[str, Any]] = await list_runbooks()

    if not inventory:
        return {"runbooks_summary": ""}

    # ── LLM call 1: which sections to open ───────────────────────────────
    selection_prompt = build_runbook_selection_prompt(
        incident_title=state["incident_title"],
        severity=state["severity"],
        summary=state["summary"],
        logs_summary=state["logs_summary"],
        runbooks=inventory,
    )

    selection: SectionsSelection = (
        await llm.with_structured_output(SectionsSelection).ainvoke(selection_prompt)
    )

    if not selection.sections:
        return {"runbooks_summary": ""}

    # ── Tool 2: load the requested sections' content ─────────────────────
    requested = [
        {"runbook_title": r.runbook_title, "section_order_index": r.section_order_index}
        for r in selection.sections
    ]
    section_chunks = await get_runbook_sections(requested)

    chunks_text = ""
    for chunk in section_chunks:
        if chunk.get("error"):
            chunks_text += f"\n--- REQUESTED {chunk['requested']['runbook_title']} [{chunk['requested']['section_order_index']}] ---\n{chunk['error']}\n"
            continue
        chunks_text += (
            f"\n--- {chunk['requested']['runbook_title']} › {chunk['heading']} ---\n"
            f"{chunk['content']}\n"
        )

    # ── LLM call 2: plain-text summary of the relevant procedures ────────
    summary_prompt = f"""You are an expert SRE. You referenced saved runbooks while resolving an active incident.

## Incident
- Title: {state["incident_title"]}
- Severity: {state["severity"]}
- Triage Summary: {state["summary"]}

## Diagnostics so far (k8s logs summary)
{state["logs_summary"]}

## Runbook Sections You Referenced
{chunks_text}

## Instructions
- Summarize the procedure(s) relevant to THIS incident in plain text
- Connect runbook guidance to the actual resources seen in the diagnostics (pod names, namespace, deployment)
- Note explicitly where the runbook guidance contradicts or does not apply to the observed evidence
- Do not use markdown headings or bullet lists
"""

    runbooks_summary: str = (await llm.ainvoke(summary_prompt)).content.strip()

    return {"runbooks_summary": runbooks_summary}
