import contextvars
from typing import Optional


# Context variable holding {"server_url": str, "token": str} loaded from the
# encrypted `credentials` table at the start of `fetch_logs`.
_cluster_credentials: contextvars.ContextVar[Optional[dict]] = contextvars.ContextVar(
    "k8s_cluster_credentials",
    default=None,
)
