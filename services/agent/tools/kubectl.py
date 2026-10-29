"""Fixed, read-only Kubernetes tools exposed to the agent.

The model can only call these functions with validated arguments. Credential
handling, command execution, TLS, timeouts, and output caps live in
``kubectl_runtime``.
"""

import json
import urllib.parse
from typing import Optional

from services.agent.tools.kubectl_runtime import (
    MAX_DEPLOYMENT_PODS,
    KubeResult,
    error_result,
    json_result,
    reset_cluster_credentials,
    run_kubectl,
    set_cluster_credentials,
    validate_limit,
    validate_name,
    validate_tail,
)

__all__ = [
    "describe_pod",
    "get_deployment",
    "get_deployment_history",
    "get_events",
    "get_pod_logs",
    "get_pod_logs_previous",
    "get_pod_status",
    "list_deployment_pods",
    "list_pods",
    "reset_cluster_credentials",
    "set_cluster_credentials",
]


def _get_deployment_data(
    namespace: str,
    deployment_name: str,
) -> tuple[Optional[dict], Optional[KubeResult]]:
    deployment_path = (
        f"/apis/apps/v1/namespaces/{urllib.parse.quote(namespace)}"
        f"/deployments/{urllib.parse.quote(deployment_name)}"
    )
    result = run_kubectl(
        [
            "kubectl",
            "get",
            "deployment",
            deployment_name,
            "-n",
            namespace,
            "-o",
            "json",
        ],
        rest_fallback_path=deployment_path,
    )
    if not result["ok"]:
        return None, result

    try:
        return json.loads(result["output"]), None
    except json.JSONDecodeError:
        return None, error_result("Kubernetes API returned invalid Deployment JSON")


def _deployment_selector(
    deployment: dict,
) -> tuple[Optional[str], Optional[KubeResult]]:
    selector = deployment.get("spec", {}).get("selector", {})
    match_labels = selector.get("matchLabels")
    if not isinstance(match_labels, dict) or not match_labels:
        return None, error_result(
            "Deployment has no matchLabels selector; pods cannot be resolved safely."
        )

    return ",".join(
        f"{key}={value}" for key, value in sorted(match_labels.items())
    ), None


def get_pod_logs(
    namespace: str,
    pod_name: str,
    tail: int = 100,
    container_name: Optional[str] = None,
) -> KubeResult:
    """Fetch current logs from one container in a pod."""
    try:
        namespace = validate_name(namespace, "namespace", 63)
        pod_name = validate_name(pod_name, "pod_name")
        tail = validate_tail(tail)
        container_name = (
            validate_name(container_name, "container_name", 63)
            if container_name
            else None
        )
    except ValueError as exc:
        return error_result(str(exc))

    ns = urllib.parse.quote(namespace)
    pod = urllib.parse.quote(pod_name)
    path = f"/api/v1/namespaces/{ns}/pods/{pod}/log?tailLines={tail}"
    args = ["kubectl", "logs", pod_name, "-n", namespace, f"--tail={tail}"]
    if container_name:
        path += f"&container={urllib.parse.quote(container_name)}"
        args.extend(["-c", container_name])

    return run_kubectl(args, rest_fallback_path=path)


def get_pod_logs_previous(
    namespace: str,
    pod_name: str,
    tail: int = 100,
    container_name: Optional[str] = None,
) -> KubeResult:
    """Fetch logs from the previous (crashed) container instance."""
    try:
        namespace = validate_name(namespace, "namespace", 63)
        pod_name = validate_name(pod_name, "pod_name")
        tail = validate_tail(tail)
        container_name = (
            validate_name(container_name, "container_name", 63)
            if container_name
            else None
        )
    except ValueError as exc:
        return error_result(str(exc))

    ns = urllib.parse.quote(namespace)
    pod = urllib.parse.quote(pod_name)
    path = f"/api/v1/namespaces/{ns}/pods/{pod}/log?previous=true&tailLines={tail}"
    args = [
        "kubectl",
        "logs",
        pod_name,
        "-n",
        namespace,
        "--previous",
        f"--tail={tail}",
    ]
    if container_name:
        path += f"&container={urllib.parse.quote(container_name)}"
        args.extend(["-c", container_name])

    return run_kubectl(args, rest_fallback_path=path)


def get_pod_status(namespace: str, pod_name: str) -> KubeResult:
    """Get the full JSON status of a pod."""
    try:
        namespace = validate_name(namespace, "namespace", 63)
        pod_name = validate_name(pod_name, "pod_name")
    except ValueError as exc:
        return error_result(str(exc))

    ns = urllib.parse.quote(namespace)
    pod = urllib.parse.quote(pod_name)
    return run_kubectl(
        ["kubectl", "get", "pod", pod_name, "-n", namespace, "-o", "json"],
        rest_fallback_path=f"/api/v1/namespaces/{ns}/pods/{pod}",
    )


def describe_pod(namespace: str, pod_name: str) -> KubeResult:
    """Get the human-readable description of a pod."""
    try:
        namespace = validate_name(namespace, "namespace", 63)
        pod_name = validate_name(pod_name, "pod_name")
    except ValueError as exc:
        return error_result(str(exc))

    ns = urllib.parse.quote(namespace)
    pod = urllib.parse.quote(pod_name)
    return run_kubectl(
        ["kubectl", "describe", "pod", pod_name, "-n", namespace],
        rest_fallback_path=f"/api/v1/namespaces/{ns}/pods/{pod}",
    )


def get_events(namespace: str) -> KubeResult:
    """List recent events in a namespace, sorted by last timestamp."""
    try:
        namespace = validate_name(namespace, "namespace", 63)
    except ValueError as exc:
        return error_result(str(exc))

    ns = urllib.parse.quote(namespace)
    return run_kubectl(
        [
            "kubectl",
            "get",
            "events",
            "-n",
            namespace,
            "--sort-by=.lastTimestamp",
        ],
        rest_fallback_path=f"/api/v1/namespaces/{ns}/events",
    )


def list_pods(namespace: str) -> KubeResult:
    """List all pods in a namespace."""
    try:
        namespace = validate_name(namespace, "namespace", 63)
    except ValueError as exc:
        return error_result(str(exc))

    ns = urllib.parse.quote(namespace)
    return run_kubectl(
        ["kubectl", "get", "pods", "-n", namespace],
        rest_fallback_path=f"/api/v1/namespaces/{ns}/pods",
    )


def get_deployment(namespace: str, deployment_name: str) -> KubeResult:
    """Get the JSON status of a deployment."""
    try:
        namespace = validate_name(namespace, "namespace", 63)
        deployment_name = validate_name(deployment_name, "deployment_name")
    except ValueError as exc:
        return error_result(str(exc))

    ns = urllib.parse.quote(namespace)
    dep = urllib.parse.quote(deployment_name)
    return run_kubectl(
        [
            "kubectl",
            "get",
            "deployment",
            deployment_name,
            "-n",
            namespace,
            "-o",
            "json",
        ],
        rest_fallback_path=f"/apis/apps/v1/namespaces/{ns}/deployments/{dep}",
    )


def list_deployment_pods(
    namespace: str,
    deployment_name: str,
    limit: int = MAX_DEPLOYMENT_PODS,
) -> KubeResult:
    """Resolve pods owned by a deployment using its trusted label selector."""
    try:
        namespace = validate_name(namespace, "namespace", 63)
        deployment_name = validate_name(deployment_name, "deployment_name")
        limit = validate_limit(limit)
    except ValueError as exc:
        return error_result(str(exc))

    deployment, error = _get_deployment_data(namespace, deployment_name)
    if error:
        return error
    assert deployment is not None

    selector, error = _deployment_selector(deployment)
    if error:
        return error
    assert selector is not None

    ns = urllib.parse.quote(namespace)
    encoded_selector = urllib.parse.quote(selector)
    result = run_kubectl(
        [
            "kubectl",
            "get",
            "pods",
            "-n",
            namespace,
            "-l",
            selector,
            "-o",
            "json",
        ],
        rest_fallback_path=(
            f"/api/v1/namespaces/{ns}/pods?labelSelector={encoded_selector}"
        ),
    )
    if not result["ok"]:
        return result

    try:
        payload = json.loads(result["output"])
    except json.JSONDecodeError:
        return error_result("Kubernetes API returned invalid Pod JSON")

    summaries = []
    for pod in payload.get("items", [])[:limit]:
        status = pod.get("status", {})
        container_statuses = status.get("containerStatuses") or []
        summaries.append(
            {
                "name": pod.get("metadata", {}).get("name"),
                "phase": status.get("phase"),
                "restarts": sum(
                    int(item.get("restartCount") or 0)
                    for item in container_statuses
                ),
                "ready": sum(1 for item in container_statuses if item.get("ready")),
                "containers": len(container_statuses),
                "node": pod.get("spec", {}).get("nodeName"),
                "created_at": pod.get("metadata", {}).get("creationTimestamp"),
            }
        )

    return json_result(
        {
            "deployment": deployment_name,
            "namespace": namespace,
            "selector": selector,
            "pods": summaries,
        }
    )


def get_deployment_history(namespace: str, deployment_name: str) -> KubeResult:
    """List replica sets and revisions associated with a deployment."""
    try:
        namespace = validate_name(namespace, "namespace", 63)
        deployment_name = validate_name(deployment_name, "deployment_name")
    except ValueError as exc:
        return error_result(str(exc))

    deployment, error = _get_deployment_data(namespace, deployment_name)
    if error:
        return error
    assert deployment is not None

    selector, error = _deployment_selector(deployment)
    if error:
        return error
    assert selector is not None

    ns = urllib.parse.quote(namespace)
    encoded_selector = urllib.parse.quote(selector)
    result = run_kubectl(
        [
            "kubectl",
            "get",
            "replicasets",
            "-n",
            namespace,
            "-l",
            selector,
            "-o",
            "json",
        ],
        rest_fallback_path=(
            f"/apis/apps/v1/namespaces/{ns}/replicasets?labelSelector={encoded_selector}"
        ),
    )
    if not result["ok"]:
        return result

    try:
        payload = json.loads(result["output"])
    except json.JSONDecodeError:
        return error_result("Kubernetes API returned invalid ReplicaSet JSON")

    revisions = []
    for replica_set in payload.get("items", []):
        metadata = replica_set.get("metadata", {})
        spec = replica_set.get("spec", {})
        status = replica_set.get("status", {})
        annotations = metadata.get("annotations") or {}
        images = [
            container.get("image")
            for container in spec.get("template", {})
            .get("spec", {})
            .get("containers", [])
        ]
        revisions.append(
            {
                "name": metadata.get("name"),
                "revision": annotations.get("deployment.kubernetes.io/revision"),
                "desired_replicas": spec.get("replicas"),
                "ready_replicas": status.get("readyReplicas", 0),
                "images": images,
                "created_at": metadata.get("creationTimestamp"),
            }
        )

    revisions.sort(
        key=lambda item: int(item.get("revision") or 0),
        reverse=True,
    )

    return json_result(
        {
            "deployment": deployment_name,
            "namespace": namespace,
            "selector": selector,
            "revisions": revisions,
        }
    )
