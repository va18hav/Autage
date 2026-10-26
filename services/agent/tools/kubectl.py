import contextvars
import json
import os
import shutil
import ssl
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

# Context variable holding {"server_url": str, "token": str, "ca_cert": str}
# loaded from the encrypted `credentials` table at the start of `fetch_logs`.
_cluster_credentials: contextvars.ContextVar[Optional[dict]] = contextvars.ContextVar(
    "k8s_cluster_credentials",
    default=None,
)


def set_cluster_credentials(creds: Optional[dict]) -> contextvars.Token:
    return _cluster_credentials.set(creds)


def reset_cluster_credentials(token: contextvars.Token) -> None:
    _cluster_credentials.reset(token)


def _http_k8s_get(
    server_url: str, token: str, path: str, ca_cert: str, accept: str = "application/json"
) -> dict:
    """Direct HTTPS call to the Kubernetes API Server (used when kubectl binary
    is not installed on the worker host).

    TLS is always verified against the cluster's CA certificate — there is no
    skip-verification path.
    """
    url = f"{server_url.rstrip('/')}{path}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            # NOTE: the Kubernetes API server rejects "Accept: text/plain" on
            # /pods/<name>/log with HTTP 406 — it always answers with a
            # text/plain body regardless, so keep the header JSON.
            "Accept": "application/json",
        },
        method="GET",
    )
    ctx = ssl.create_default_context(cadata=ca_cert)
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
    the ServiceAccount token + Cluster API URL + CA certificate from the DB if
    present). TLS verification is mandatory: without a stored CA certificate no
    DB-configured path is used at all. Falls back to a bare local kubectl
    (ambient kubeconfig, which carries its own CA) when no cluster is configured.
    """
    creds = _cluster_credentials.get()
    has_db_cluster = bool(
        creds and creds.get("server_url") and creds.get("token") and creds.get("ca_cert")
    )

    if has_db_cluster:
        server_url = str(creds["server_url"]).strip().rstrip("/")
        token = str(creds["token"]).strip()
        ca_cert = str(creds["ca_cert"]).strip()

        # If kubectl CLI is available on the host, pass --server, --token, and
        # the CA certificate (written to a 0600 temp file for the subprocess).
        if shutil.which("kubectl"):
            fd, ca_path = tempfile.mkstemp(prefix="autage-ca-", suffix=".pem")
            try:
                os.fchmod(fd, 0o600)
                with os.fdopen(fd, "w") as f:
                    f.write(ca_cert)
                auth_args = [
                    *args,
                    f"--server={server_url}",
                    f"--token={token}",
                    f"--certificate-authority={ca_path}",
                ]
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
            finally:
                try:
                    os.unlink(ca_path)
                except OSError:
                    pass

        # Fallback: direct HTTPS call to the Kubernetes API Server if kubectl is not installed
        if rest_fallback_path:
            return _http_k8s_get(server_url, token, rest_fallback_path, ca_cert, accept=accept)

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


def get_events(namespace: str) -> dict:
    """
    Lists recent events in the namespace sorted by time.
    Good for spotting evictions, scheduling failures, image pull errors.
    kubectl get events -n <namespace> --sort-by=.lastTimestamp
    """
    ns = urllib.parse.quote(namespace)
    return _run(
        ["kubectl", "get", "events", "-n", namespace, "--sort-by=.lastTimestamp"],
        rest_fallback_path=f"/api/v1/namespaces/{ns}/events",
    )


def list_pods(namespace: str) -> dict:
    """
    Lists all pods in a namespace with their status.
    kubectl get pods -n <namespace>
    """
    ns = urllib.parse.quote(namespace)
    return _run(
        ["kubectl", "get", "pods", "-n", namespace],
        rest_fallback_path=f"/api/v1/namespaces/{ns}/pods",
    )


def get_deployment(namespace: str, deployment_name: str) -> dict:
    """
    Gets the JSON status of a deployment — desired vs available replicas,
    rollout strategy, conditions.
    kubectl get deployment <deployment_name> -n <namespace> -o json
    """
    ns = urllib.parse.quote(namespace)
    dep = urllib.parse.quote(deployment_name)
    return _run(
        ["kubectl", "get", "deployment", deployment_name, "-n", namespace, "-o", "json"],
        rest_fallback_path=f"/apis/apps/v1/namespaces/{ns}/deployments/{dep}",
    )
