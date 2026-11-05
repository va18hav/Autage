"""Shared plumbing for read-only Kubernetes API calls.

Credentials live in a ContextVar, so each incident uses its own cluster and
nothing leaks between concurrent runs. Every call is read-only, bounded by a
timeout, and truncated before it reaches the model.
"""

import ssl
import urllib.error
import urllib.request
from contextvars import ContextVar
from typing import Any

from services.secrets.store import SecretStore

_KUBERNETES_PURPOSE = "kubernetes"
_REQUIRED_FIELDS = ("server_url", "token", "ca_cert")
_TIMEOUT_SECONDS = 20
_MAX_OUTPUT_CHARS = 12_000

# One cluster connection: {"server_url", "token", "ca_cert"} or None.
_cluster: ContextVar[dict[str, str] | None] = ContextVar("k8s_cluster", default=None)


async def load_cluster_credentials() -> dict[str, str] | None:
    """Read the saved cluster; None means no cluster is configured."""
    payload = await SecretStore.fetch_payload(_KUBERNETES_PURPOSE)
    return payload if isinstance(payload, dict) else None


def require_cluster() -> dict[str, str]:
    """Return complete credentials or raise a short, safe error."""
    cluster = _cluster.get()
    if not cluster:
        raise ValueError("Kubernetes cluster is not configured.")
    missing = [k for k in _REQUIRED_FIELDS if not str(cluster.get(k) or "").strip()]
    if missing:
        raise ValueError(f"Kubernetes credentials are incomplete: {', '.join(missing)}.")
    return cluster


def set_cluster_credentials(payload: dict[str, str] | None):
    """Make `payload` the active cluster for this request; returns a reset token."""
    return _cluster.set(payload)


def reset_cluster_credentials(token) -> None:
    """Restore the previous credentials after the step finishes."""
    _cluster.reset(token)


def k8s_get(path: str) -> dict[str, Any]:
    """GET one read-only Kubernetes API path using the active cluster."""
    if not path.startswith("/"):
        return _failure("Kubernetes API path must start with '/'.")
    try:
        cluster = require_cluster()
    except ValueError as exc:
        return _failure(str(exc))

    return _http_k8s_get(
        cluster["server_url"],
        cluster["token"],
        path,
        cluster["ca_cert"].strip(),
    )


def _http_k8s_get(
    server_url: str, token: str, path: str, ca_cert: str
) -> dict[str, Any]:
    """Make one HTTPS GET and return a standard evidence result."""
    url = server_url.strip().rstrip("/") + path
    try:
        context = ssl.create_default_context(cadata=ca_cert)
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token.strip()}",
                "Accept": "application/json, text/plain, */*",
            },
            method="GET",
        )
        with urllib.request.urlopen(
            request, context=context, timeout=_TIMEOUT_SECONDS
        ) as response:
            body = response.read().decode("utf-8", errors="replace")
        return _success(_redact(body, token))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace").strip()
        message = f"Kubernetes API returned HTTP {exc.code}"
        if body:
            message = f"{message}: {body}"
        return _failure(_redact(message, token))
    except urllib.error.URLError as exc:
        reason = _redact(str(exc.reason), token)
        return _failure(f"Could not reach the Kubernetes API: {reason}")
    except Exception as exc:  # TLS errors, malformed CA, or an invalid URL
        detail = _redact(str(exc), token)
        return _failure(f"Kubernetes API request failed: {detail}")


def success_result(text: str) -> dict[str, Any]:
    """Wrap plain text in the standard evidence shape."""
    return _success(text)


def failure_result(message: str) -> dict[str, Any]:
    """Wrap an error message in the standard evidence shape."""
    return _failure(message)


def _redact(text: str, token: str) -> str:
    """Remove the service-account token from anything we may show or log."""
    token = token.strip()
    return text.replace(token, "***") if token else text


def _success(text: str) -> dict[str, Any]:
    clipped, truncated = _clip(text)
    return {"ok": True, "output": clipped, "error": None, "truncated": truncated}


def _failure(message: str) -> dict[str, Any]:
    return {"ok": False, "output": "", "error": message.strip(), "truncated": False}


def _clip(text: str) -> tuple[str, bool]:
    """Keep evidence short enough to fit comfortably in a model prompt."""
    if len(text) <= _MAX_OUTPUT_CHARS:
        return text, False
    return text[:_MAX_OUTPUT_CHARS] + "\n… [truncated]", True
