import contextvars
import shutil
import ssl
import subprocess
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


def _run(args: list[str], rest_fallback_path: Optional[str] = None, accept: str = "application/json") -> dict:
    """
    Executes a kubectl command against the configured Kubernetes cluster (using
    the ServiceAccount token + Cluster API URL from the DB if present).
    Falls back to mock responses when no cluster is configured in DB and
    MOCK_KUBECTL=true.
    """
    creds = _cluster_credentials.get()
    has_db_cluster = bool(creds and creds.get("server_url") and creds.get("token"))

    if not has_db_cluster and settings.MOCK_KUBECTL:
        from services.agent.mock.kubectl_responses import get_mock_response
        return get_mock_response(args)

    if has_db_cluster:
        server_url = str(creds["server_url"]).strip().rstrip("/")
        token = str(creds["token"]).strip()

        # If kubectl CLI is available on the host, pass --server and --token
        if shutil.which("kubectl"):
            auth_args = [
                *args,
                f"--server={server_url}",
                f"--token={token}",
            ]
            if not settings.K8S_VERIFY_SSL:
                auth_args.append("--insecure-skip-tls-verify=true")
            try:
                result = subprocess.run(
                    auth_args,
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                err = result.stderr.replace(token, "***") if result.stderr else None
                return {
                    "ok": result.returncode == 0,
                    "output": result.stdout,
                    "error": err if result.returncode != 0 else None,
                }
            except subprocess.TimeoutExpired:
                return {"ok": False, "output": "", "error": "kubectl command timed out after 20s"}

        # Fallback: direct HTTPS call to the Kubernetes API Server if kubectl is not installed
        if rest_fallback_path:
            return _http_k8s_get(server_url, token, rest_fallback_path, accept=accept)

    # Local/in-cluster default kubectl execution
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=20,
        )
        return {
            "ok": result.returncode == 0,
            "output": result.stdout,
            "error": result.stderr if result.returncode != 0 else None,
        }
    except FileNotFoundError:
        return {
            "ok": False,
            "output": "",
            "error": "kubectl binary not found on host and no cluster configured in Integrations.",
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "output": "", "error": "kubectl command timed out after 20s"}


def get_pod_logs(namespace: str, pod_name: str, tail: int = 100) -> dict:
    """
    Fetches the last `tail` lines of logs from a pod.
    kubectl logs <pod_name> -n <namespace> --tail=<tail>
    """
    ns = urllib.parse.quote(namespace)
    pod = urllib.parse.quote(pod_name)
    return _run(
        ["kubectl", "logs", pod_name, "-n", namespace, f"--tail={tail}"],
        rest_fallback_path=f"/api/v1/namespaces/{ns}/pods/{pod}/log?tailLines={tail}",
        accept="text/plain",
    )


def get_pod_logs_previous(namespace: str, pod_name: str, tail: int = 100) -> dict:
    """
    Fetches logs from the *previous* (crashed) container instance.
    Useful for OOMKills and CrashLoopBackOffs.
    kubectl logs <pod_name> -n <namespace> --previous --tail=<tail>
    """
    ns = urllib.parse.quote(namespace)
    pod = urllib.parse.quote(pod_name)
    return _run(
        ["kubectl", "logs", pod_name, "-n", namespace, "--previous", f"--tail={tail}"],
        rest_fallback_path=f"/api/v1/namespaces/{ns}/pods/{pod}/log?previous=true&tailLines={tail}",
        accept="text/plain",
    )


def get_pod_status(namespace: str, pod_name: str) -> dict:
    """
    Gets the full JSON status of a pod — phase, conditions, container states.
    kubectl get pod <pod_name> -n <namespace> -o json
    """
    ns = urllib.parse.quote(namespace)
    pod = urllib.parse.quote(pod_name)
    return _run(
        ["kubectl", "get", "pod", pod_name, "-n", namespace, "-o", "json"],
        rest_fallback_path=f"/api/v1/namespaces/{ns}/pods/{pod}",
    )


def describe_pod(namespace: str, pod_name: str) -> dict:
    """
    Human-readable pod description — events, resource limits, restart count,
    liveness/readiness probe failures, OOMKill reasons.
    kubectl describe pod <pod_name> -n <namespace>
    """
    ns = urllib.parse.quote(namespace)
    pod = urllib.parse.quote(pod_name)
    return _run(
        ["kubectl", "describe", "pod", pod_name, "-n", namespace],
        rest_fallback_path=f"/api/v1/namespaces/{ns}/pods/{pod}",
    )
