from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field

from services.agent.tools.kubectl import get_pod_logs, get_pod_logs_previous, get_pod_status, describe_pod, get_events, list_pods, get_deployment


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
