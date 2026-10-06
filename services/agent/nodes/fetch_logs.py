from typing import Dict, Any, Optional, List
from enum import Enum
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from sqlalchemy import func, select

from services.agent.state import AgentState
from services.agent.prompts.fetch_logs import build_plan_prompt, build_summary_prompt
from services.agent.nodes.trace_step import traced_step
from services.agent.tools.kubectl import (
    get_pod_logs,
    get_pod_logs_previous,
    get_pod_status,
    describe_pod,
    get_events,
    list_pods,
    get_deployment,
)
from services.db.database import async_session_factory
from services.db.models.runbooks import Runbook


# ── Structured output models ──────────────────────────────────────────────────

class KubectlTool(str, Enum):
    GET_POD_LOGS          = "get_pod_logs"
    GET_POD_LOGS_PREVIOUS = "get_pod_logs_previous"
    GET_POD_STATUS        = "get_pod_status"
    DESCRIBE_POD          = "describe_pod"
    GET_EVENTS            = "get_events"
    LIST_PODS             = "list_pods"
    GET_DEPLOYMENT        = "get_deployment"


class KubectlCommand(BaseModel):
    """A single kubectl command the LLM wants to run."""
    tool: KubectlTool         = Field(description="The tool/function to call")
    namespace: str            = Field(description="Kubernetes namespace to target")
    pod_name: Optional[str]   = Field(default=None, description="Pod name — required for pod-specific tools")
    deployment_name: Optional[str] = Field(default=None, description="Deployment name — required for get_deployment")
    tail: Optional[int]       = Field(default=100, description="Number of log lines to fetch (log tools only)")


class KubectlPlan(BaseModel):
    """LLM's plan: which commands to run, and whether runbooks should be consulted."""
    reasoning: str                  = Field(description="Brief reasoning for why these tools were chosen")
    runbooks_needed: bool           = Field(description="True only when curated runbooks likely hold the remediation procedure AND runbooks exist")
    commands: List[KubectlCommand]  = Field(description="List of kubectl commands to execute")


# ── Tool dispatcher ───────────────────────────────────────────────────────────

# Maps each KubectlTool enum value to the actual function call.
# The node uses this to execute whatever the LLM decided to run.
TOOL_DISPATCHER = {
    KubectlTool.GET_POD_LOGS: lambda cmd: get_pod_logs(
        namespace=cmd.namespace,
        pod_name=cmd.pod_name,
        tail=cmd.tail or 100,
    ),
    KubectlTool.GET_POD_LOGS_PREVIOUS: lambda cmd: get_pod_logs_previous(
        namespace=cmd.namespace,
        pod_name=cmd.pod_name,
        tail=cmd.tail or 100,
    ),
    KubectlTool.GET_POD_STATUS: lambda cmd: get_pod_status(
        namespace=cmd.namespace,
        pod_name=cmd.pod_name,
    ),
    KubectlTool.DESCRIBE_POD: lambda cmd: describe_pod(
        namespace=cmd.namespace,
        pod_name=cmd.pod_name,
    ),
    KubectlTool.GET_EVENTS: lambda cmd: get_events(
        namespace=cmd.namespace,
    ),
    KubectlTool.LIST_PODS: lambda cmd: list_pods(
        namespace=cmd.namespace,
    ),
    KubectlTool.GET_DEPLOYMENT: lambda cmd: get_deployment(
        namespace=cmd.namespace,
        deployment_name=cmd.deployment_name,
    ),
}


# ── Node ──────────────────────────────────────────────────────────────────────

@traced_step("fetch_logs")
async def fetch_logs(state: AgentState) -> Dict[str, Any]:
    """
    Fetch logs node (renamed from context gathering).

    Check whether runbooks exist in the DB so runbooks_needed is only ever
    meaningful when there is something to consult.
    Step 1 — LLM reads the raw_alert and decides which kubectl commands to run.
    Step 2 — Node executes those commands using the tool dispatcher.
    Step 3 — LLM reads all outputs and produces a plain-text summary.
    """
    llm = ChatGoogleGenerativeAI(model="gemini-3.7-flash", temperature=0)

    # Runbook presence check — a cheap count, done here so both the worker and
    # standalone main.py runs get the same behavior.
    async with async_session_factory() as db:
        runbook_count = (
            await db.execute(select(func.count()).select_from(Runbook))
        ).scalar_one()
    runbooks_available = runbook_count > 0

    # ── Step 1: Ask LLM which commands to run + whether runbooks are needed ──
    plan_prompt = build_plan_prompt(
        raw_alert=state["raw_alert"],
        incident_title=state["incident_title"],
        severity=state["severity"],
        summary=state["summary"],
        runbooks_available=runbooks_available,
    )

    plan_llm = llm.with_structured_output(KubectlPlan)
    plan: KubectlPlan = await plan_llm.ainvoke(plan_prompt)

    runbooks_needed = bool(runbooks_available and plan.runbooks_needed)

    # ── Step 2: Execute each command the LLM chose ───────────────────────
    logs: Dict[str, Any] = {}
    errors: List[str] = []

    for cmd in plan.commands:
        # Build a unique key for each result, e.g. "get_pod_logs:auth-service-xyz"
        key_suffix = cmd.pod_name or cmd.deployment_name or cmd.namespace
        result_key = f"{cmd.tool.value}:{key_suffix}"

        executor = TOOL_DISPATCHER.get(cmd.tool)
        if executor is None:
            errors.append(f"Unknown tool requested by LLM: {cmd.tool}")
            continue

        result = executor(cmd)
        logs[result_key] = result

        if not result["ok"]:
            errors.append(f"{result_key} failed: {result['error']}")

    # ── Step 3: Ask LLM to summarize all outputs (plain text — keep it simple) ──
    summary_prompt = build_summary_prompt(
        incident_title=state["incident_title"],
        severity=state["severity"],
        summary=state["summary"],
        logs=logs,
    )

    # ── Step 3: Ask LLM to summarize all outputs (plain text — keep it simple) ──
    logs_summary: str = (await llm.ainvoke(summary_prompt)).content.strip()

    return {
        "logs": logs,
        "logs_summary": logs_summary,
        "runbooks_available": runbooks_available,
        "runbooks_needed": runbooks_needed,
    }
