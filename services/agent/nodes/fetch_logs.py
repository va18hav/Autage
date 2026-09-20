from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field



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
