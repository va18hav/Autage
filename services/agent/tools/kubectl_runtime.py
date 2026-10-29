"""Kubernetes execution and safety primitives.

This module owns everything that can touch a cluster: credentials, argument
validation, kubeconfig creation, subprocess execution, REST fallback, TLS,
timeouts, redaction, and output limits.

Read-only tool definitions live in ``services.agent.tools.kubectl``.
"""

import base64
import contextvars
import json
import os
import re
import shutil
import ssl
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional, TypedDict

KUBECTL_TIMEOUT_SECONDS = 20
REST_TIMEOUT_SECONDS = 15
MAX_OUTPUT_CHARS = 150_000
MAX_ERROR_CHARS = 4_000
MAX_LOG_TAIL = 1_000
MAX_DEPLOYMENT_PODS = 50

_LABEL_RE = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")

# {"server_url": str, "token": str, "ca_cert": str}, loaded from the encrypted
# credentials table before evidence collection.
_cluster_credentials: contextvars.ContextVar[Optional[dict]] = contextvars.ContextVar(
    "k8s_cluster_credentials",
    default=None,
)


class KubeResult(TypedDict):
    ok: bool
    output: str
    error: Optional[str]
    truncated: bool


def set_cluster_credentials(creds: Optional[dict]) -> contextvars.Token:
    return _cluster_credentials.set(creds)


def reset_cluster_credentials(token: contextvars.Token) -> None:
    _cluster_credentials.reset(token)


def result(
    ok: bool,
    output: str = "",
    error: Optional[str] = None,
    truncated: bool = False,
) -> KubeResult:
    return {
        "ok": ok,
        "output": output,
        "error": error,
        "truncated": truncated,
    }


def error_result(message: str) -> KubeResult:
    return result(False, error=message)


def truncate_output(text: str, limit: int = MAX_OUTPUT_CHARS) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit] + "\n...[output truncated by Autage]", True


def json_result(data: Any) -> KubeResult:
    output = json.dumps(data, indent=2, sort_keys=True)
    output, truncated = truncate_output(output)
    return result(True, output=output, truncated=truncated)


def _redact(text: Optional[str], token: Optional[str]) -> Optional[str]:
    if not text:
        return text
    if token:
        return text.replace(token, "***")
    return text


def validate_name(value: str, field: str, max_length: int = 253) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")

    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field} is required")
    if len(cleaned) > max_length:
        raise ValueError(f"{field} is longer than {max_length} characters")

    for label in cleaned.split("."):
        if not _LABEL_RE.fullmatch(label):
            raise ValueError(f"{field} is not a valid Kubernetes name")

    return cleaned


def validate_tail(tail: int) -> int:
    if isinstance(tail, bool) or not isinstance(tail, int):
        raise ValueError("tail must be an integer")
    if not 1 <= tail <= MAX_LOG_TAIL:
        raise ValueError(f"tail must be between 1 and {MAX_LOG_TAIL}")
    return tail


def validate_limit(limit: int, maximum: int = MAX_DEPLOYMENT_PODS) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ValueError("limit must be an integer")
    if not 1 <= limit <= maximum:
        raise ValueError(f"limit must be between 1 and {maximum}")
    return limit


def _configured_credentials() -> tuple[Optional[dict], Optional[KubeResult]]:
    """Return complete credentials or a fail-closed error result."""
    creds = _cluster_credentials.get()
    if not creds:
        return None, error_result(
            "Kubernetes cluster is not configured. Add a cluster in Integrations before running diagnostics."
        )

    server_url = str(creds.get("server_url") or "").strip().rstrip("/")
    token = str(creds.get("token") or "").strip()
    ca_cert = str(creds.get("ca_cert") or "").strip()

    if not server_url or not token or not ca_cert:
        return None, error_result(
            "Kubernetes cluster configuration is incomplete. A server URL, token, and CA certificate are required."
        )

    parsed = urllib.parse.urlsplit(server_url)
    if parsed.scheme != "https" or not parsed.netloc:
        return None, error_result("Kubernetes server URL must be a valid HTTPS URL.")

    return {
        "server_url": server_url,
        "token": token,
        "ca_cert": ca_cert,
    }, None


def _http_k8s_get(
    server_url: str,
    token: str,
    path: str,
    ca_cert: str,
) -> KubeResult:
    """Direct HTTPS call to the Kubernetes API Server.

    TLS is always verified against the cluster's CA certificate. There is no
    skip-verification path.
    """
    url = f"{server_url.rstrip('/')}{path}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            # The Kubernetes API server rejects "Accept: text/plain" on
            # /pods/<name>/log with HTTP 406, even though the body is text.
            "Accept": "application/json",
        },
        method="GET",
    )
    ctx = ssl.create_default_context(cadata=ca_cert)
    try:
        with urllib.request.urlopen(
            req,
            context=ctx,
            timeout=REST_TIMEOUT_SECONDS,
        ) as response:
            raw = response.read().decode("utf-8", errors="replace")
            output, truncated = truncate_output(raw)
            return result(True, output=output, truncated=truncated)
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        err_body, truncated = truncate_output(err_body, MAX_ERROR_CHARS)
        return result(
            False,
            error=f"HTTP {exc.code}: {_redact(err_body, token)}",
            truncated=truncated,
        )
    except Exception as exc:
        return error_result(
            _redact(str(exc), token) or "Kubernetes API request failed"
        )


def _kubeconfig_file(server_url: str, token: str, ca_cert: str) -> str:
    """Write a temporary kubeconfig so the token never appears in argv."""
    encoded_ca = base64.b64encode(ca_cert.encode("utf-8")).decode("ascii")
    config = {
        "apiVersion": "v1",
        "kind": "Config",
        "clusters": [
            {
                "name": "autage",
                "cluster": {
                    "server": server_url,
                    "certificate-authority-data": encoded_ca,
                },
            }
        ],
        "users": [{"name": "autage", "user": {"token": token}}],
        "contexts": [
            {
                "name": "autage",
                "context": {"cluster": "autage", "user": "autage"},
            }
        ],
        "current-context": "autage",
    }

    fd, path = tempfile.mkstemp(prefix="autage-kubeconfig-", suffix=".json")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as handle:
            json.dump(config, handle)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(path)
        except OSError:
            pass
        raise

    return path


def run_kubectl(
    args: list[str],
    rest_fallback_path: Optional[str] = None,
) -> KubeResult:
    """Run a fixed kubectl argument list against the configured cluster.

    This fails closed when cluster credentials are missing or incomplete. It
    never falls back to the worker host's local kubeconfig.
    """
    creds, error = _configured_credentials()
    if error:
        return error

    assert creds is not None
    server_url = creds["server_url"]
    token = creds["token"]
    ca_cert = creds["ca_cert"]

    if shutil.which("kubectl"):
        kubeconfig_path: Optional[str] = None
        try:
            kubeconfig_path = _kubeconfig_file(server_url, token, ca_cert)
            env = os.environ.copy()
            env["KUBECONFIG"] = kubeconfig_path

            completed = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=KUBECTL_TIMEOUT_SECONDS,
                env=env,
            )

            if completed.returncode != 0:
                stderr = (
                    _redact(completed.stderr, token) or "kubectl command failed"
                )
                stderr, truncated = truncate_output(stderr, MAX_ERROR_CHARS)
                return result(False, error=stderr, truncated=truncated)

            stdout = _redact(completed.stdout, token) or ""
            output, truncated = truncate_output(stdout)
            return result(True, output=output, truncated=truncated)
        except subprocess.TimeoutExpired:
            return error_result(
                f"kubectl command timed out after {KUBECTL_TIMEOUT_SECONDS}s"
            )
        except Exception as exc:
            return error_result(_redact(str(exc), token) or "kubectl command failed")
        finally:
            if kubeconfig_path:
                try:
                    os.unlink(kubeconfig_path)
                except OSError:
                    pass

    if rest_fallback_path:
        return _http_k8s_get(server_url, token, rest_fallback_path, ca_cert)

    return error_result(
        "kubectl binary is not installed and this operation has no REST fallback."
    )
