import contextvars
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

from services.config import settings

# Context variable holding {"server_url": str, "token": str} loaded from the
# encrypted `credentials` table at the start of `fetch_logs`.
_cluster_credentials: contextvars.ContextVar[Optional[dict]] = contextvars.ContextVar(
    "k8s_cluster_credentials",
    default=None,
)


def set_cluster_credentials(creds: Optional[dict]) -> contextvars.Token:
    return _cluster_credentials.set(creds)


def reset_cluster_credentials(token: contextvars.Token) -> None:
    _cluster_credentials.reset(token)


def _http_k8s_get(server_url: str, token: str, path: str, accept: str = "application/json") -> dict:
    """Direct HTTPS call to the Kubernetes API Server (used when kubectl binary
    is not installed on the worker host)."""
    url = f"{server_url.rstrip('/')}{path}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": accept,
        },
        method="GET",
    )
    ctx = (
        ssl.create_default_context()
        if settings.K8S_VERIFY_SSL
        else ssl._create_unverified_context()
    )
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return {"ok": True, "output": raw, "error": None}
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        return {"ok": False, "output": "", "error": f"HTTP {exc.code}: {err_body}"}
    except Exception as exc:
        return {"ok": False, "output": "", "error": str(exc)}
