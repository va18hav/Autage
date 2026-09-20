from enum import Enum



# ── Structured output models ──────────────────────────────────────────────────

class KubectlTool(str, Enum):
    GET_POD_LOGS          = "get_pod_logs"
    GET_POD_LOGS_PREVIOUS = "get_pod_logs_previous"
    GET_POD_STATUS        = "get_pod_status"
    DESCRIBE_POD          = "describe_pod"
    GET_EVENTS            = "get_events"
    LIST_PODS             = "list_pods"
    GET_DEPLOYMENT        = "get_deployment"
