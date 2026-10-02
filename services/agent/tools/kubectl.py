from services.config import settings
import subprocess
from typing import Optional


def _run(args: list[str]) -> dict:
    """
    Base runner. Executes any kubectl command as a subprocess.
    If MOCK_KUBECTL=true is set in the environment, returns pre-canned
    mock responses instead of hitting a real cluster.
    Returns a dict with ok (bool), output (str), and error (str).
    """
    if settings.MOCK_KUBECTL:
        from services.agent.mock.kubectl_responses import get_mock_response
        return get_mock_response(args)

    result = subprocess.run(
        args,
        capture_output=True,
        text=True
    )
    return {
        "ok": result.returncode == 0,
        "output": result.stdout,
        "error": result.stderr if result.returncode != 0 else None
    }


def get_pod_logs(namespace: str, pod_name: str, tail: int = 100) -> dict:
    """
    Fetches the last `tail` lines of logs from a pod.
    kubectl logs <pod_name> -n <namespace> --tail=<tail>
    """
    return _run(["kubectl", "logs", pod_name, "-n", namespace, f"--tail={tail}"])


def get_pod_logs_previous(namespace: str, pod_name: str, tail: int = 100) -> dict:
    """
    Fetches logs from the *previous* (crashed) container instance.
    Useful for OOMKills and CrashLoopBackOffs.
    kubectl logs <pod_name> -n <namespace> --previous --tail=<tail>
    """
    return _run(["kubectl", "logs", pod_name, "-n", namespace, "--previous", f"--tail={tail}"])


def get_pod_status(namespace: str, pod_name: str) -> dict:
    """
    Gets the full JSON status of a pod — phase, conditions, container states.
    kubectl get pod <pod_name> -n <namespace> -o json
    """
    return _run(["kubectl", "get", "pod", pod_name, "-n", namespace, "-o", "json"])


def describe_pod(namespace: str, pod_name: str) -> dict:
    """
    Human-readable pod description — events, resource limits, restart count,
    liveness/readiness probe failures, OOMKill reasons.
    kubectl describe pod <pod_name> -n <namespace>
    """
    return _run(["kubectl", "describe", "pod", pod_name, "-n", namespace])


def get_events(namespace: str) -> dict:
    """
    Lists recent events in the namespace sorted by time.
    Good for spotting evictions, scheduling failures, image pull errors.
    kubectl get events -n <namespace> --sort-by=.lastTimestamp
    """
    return _run(["kubectl", "get", "events", "-n", namespace, "--sort-by=.lastTimestamp"])


def list_pods(namespace: str) -> dict:
    """
    Lists all pods in a namespace with their status.
    kubectl get pods -n <namespace>
    """
    return _run(["kubectl", "get", "pods", "-n", namespace])


def get_deployment(namespace: str, deployment_name: str) -> dict:
    """
    Gets the JSON status of a deployment — desired vs available replicas,
    rollout strategy, conditions.
    kubectl get deployment <deployment_name> -n <namespace> -o json
    """
    return _run(["kubectl", "get", "deployment", deployment_name, "-n", namespace, "-o", "json"])
