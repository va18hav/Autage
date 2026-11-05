"""Read-only Kubernetes evidence tools.

Every function returns the same evidence shape used by the agent:

    {"ok": bool, "output": str, "error": str | None, "truncated": bool}
"""

import json
import re
from typing import Any
from urllib.parse import urlencode

from services.agent.tools.k8s_runtime import (
    failure_result,
    k8s_get,
    success_result,
)

_DNS_LABEL = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
_DNS_SUBDOMAIN = re.compile(
    r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*$"
)
_DEFAULT_LOG_TAIL = 200
_MAX_LOG_TAIL = 5000


def get_pod_status(namespace: str, pod_name: str) -> dict[str, Any]:
    """Read one pod's phase, container states, and conditions."""
    error = _validate(namespace, "namespace") or _validate(
        pod_name, "pod_name", subdomain=True
    )
    if error:
        return failure_result(error)

    data, result = _get_json(f"/api/v1/namespaces/{namespace}/pods/{pod_name}")
    if data is None:
        return result

    metadata = data.get("metadata") or {}
    status = data.get("status") or {}
    return success_result(
        _json_text(
            {
                "name": metadata.get("name"),
                "phase": status.get("phase"),
                "node": (data.get("spec") or {}).get("nodeName"),
                "containers": [
                    _container_status(item)
                    for item in status.get("containerStatuses") or []
                ],
                "conditions": status.get("conditions") or [],
            }
        )
    )


def get_pod_logs(
    namespace: str,
    pod_name: str,
    *,
    tail: int = _DEFAULT_LOG_TAIL,
    container: str | None = None,
) -> dict[str, Any]:
    """Read the current container logs for one pod."""
    return _pod_logs(
        namespace, pod_name, tail=tail, container=container, previous=False
    )


def get_pod_logs_previous(
    namespace: str,
    pod_name: str,
    *,
    tail: int = _DEFAULT_LOG_TAIL,
    container: str | None = None,
) -> dict[str, Any]:
    """Read the logs from the container instance that crashed."""
    return _pod_logs(
        namespace, pod_name, tail=tail, container=container, previous=True
    )


def _pod_logs(
    namespace: str,
    pod_name: str,
    *,
    tail: int,
    container: str | None,
    previous: bool,
) -> dict[str, Any]:
    error = _validate(namespace, "namespace") or _validate(
        pod_name, "pod_name", subdomain=True
    )
    if error:
        return failure_result(error)

    if not isinstance(tail, int) or not 1 <= tail <= _MAX_LOG_TAIL:
        return failure_result(
            f"Invalid tail: use an integer between 1 and {_MAX_LOG_TAIL}."
        )

    if container is not None:
        error = _validate(container, "container")
        if error:
            return failure_result(error)

    query = {"tailLines": str(tail)}
    if previous:
        query["previous"] = "true"
    if container:
        query["container"] = container

    path = (
        f"/api/v1/namespaces/{namespace}/pods/{pod_name}/log?"
        f"{urlencode(query)}"
    )
    return k8s_get(path)


def get_deployment(namespace: str, deployment_name: str) -> dict[str, Any]:
    """Read desired replicas, rollout state, conditions, and images."""
    error = _validate(namespace, "namespace") or _validate(
        deployment_name, "deployment_name", subdomain=True
    )
    if error:
        return failure_result(error)

    data, result = _get_deployment(namespace, deployment_name)
    if data is None:
        return result

    return success_result(_json_text(_deployment_summary(data)))


def list_deployment_pods(namespace: str, deployment_name: str) -> dict[str, Any]:
    """List the pods selected by a deployment, with readiness and restart counts."""
    error = _validate(namespace, "namespace") or _validate(
        deployment_name, "deployment_name", subdomain=True
    )
    if error:
        return failure_result(error)

    data, result = _get_deployment(namespace, deployment_name)
    if data is None:
        return result

    selector = _selector_from_deployment(data)
    if selector is None:
        return failure_result("Deployment has no matchLabels selector.")

    query = urlencode({"labelSelector": selector})
    pods, result = _get_json(
        f"/api/v1/namespaces/{namespace}/pods?{query}"
    )
    if pods is None:
        return result

    return success_result(
        _json_text(
            {
                "deployment": deployment_name,
                "selector": selector,
                "pods": [_pod_summary(item) for item in pods.get("items") or []],
            }
        )
    )


def get_deployment_history(namespace: str, deployment_name: str) -> dict[str, Any]:
    """Read deployment revisions from the ReplicaSets it owns."""
    error = _validate(namespace, "namespace") or _validate(
        deployment_name, "deployment_name", subdomain=True
    )
    if error:
        return failure_result(error)

    data, result = _get_deployment(namespace, deployment_name)
    if data is None:
        return result

    selector = _selector_from_deployment(data)
    if selector is None:
        return failure_result("Deployment has no matchLabels selector.")

    annotations = (data.get("metadata") or {}).get("annotations") or {}
    query = urlencode({"labelSelector": selector})
    replicasets, result = _get_json(
        f"/apis/apps/v1/namespaces/{namespace}/replicasets?{query}"
    )
    if replicasets is None:
        return result

    revisions = []
    for replicaset in replicasets.get("items") or []:
        metadata = replicaset.get("metadata") or {}
        rs_annotations = metadata.get("annotations") or {}
        status = replicaset.get("status") or {}
        revisions.append(
            {
                "replicaset": metadata.get("name"),
                "revision": rs_annotations.get("deployment.kubernetes.io/revision"),
                "desired_replicas": (replicaset.get("spec") or {}).get("replicas"),
                "ready_replicas": status.get("readyReplicas", 0),
                "available_replicas": status.get("availableReplicas", 0),
                "created": metadata.get("creationTimestamp"),
                "images": _images(replicaset),
            }
        )

    revisions.sort(key=lambda item: int(item["revision"] or 0), reverse=True)

    return success_result(
        _json_text(
            {
                "deployment": deployment_name,
                "current_revision": annotations.get(
                    "deployment.kubernetes.io/revision"
                ),
                "revisions": revisions,
            }
        )
    )


def get_events(namespace: str) -> dict[str, Any]:
    """Read recent Warning events in a namespace."""
    error = _validate(namespace, "namespace")
    if error:
        return failure_result(error)

    query = urlencode({"fieldSelector": "type=Warning", "limit": "100"})
    data, result = _get_json(f"/api/v1/namespaces/{namespace}/events?{query}")
    if data is None:
        return result

    events = []
    for event in data.get("items") or []:
        involved = event.get("involvedObject") or {}
        kind = involved.get("kind") or ""
        name = involved.get("name") or ""
        events.append(
            {
                "type": event.get("type"),
                "reason": event.get("reason"),
                "message": event.get("message"),
                "count": event.get("count"),
                "last_timestamp": event.get("lastTimestamp"),
                "object": f"{kind}/{name}".strip("/"),
            }
        )

    return success_result(
        _json_text({"namespace": namespace, "events": events})
    )


def _get_deployment(
    namespace: str, deployment_name: str
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    return _get_json(
        f"/apis/apps/v1/namespaces/{namespace}/deployments/{deployment_name}"
    )


def _deployment_summary(data: dict[str, Any]) -> dict[str, Any]:
    metadata = data.get("metadata") or {}
    spec = data.get("spec") or {}
    status = data.get("status") or {}
    template_spec = (spec.get("template") or {}).get("spec") or {}

    return {
        "name": metadata.get("name"),
        "generation": metadata.get("generation"),
        "observed_generation": status.get("observedGeneration"),
        "desired_replicas": spec.get("replicas"),
        "updated_replicas": status.get("updatedReplicas"),
        "ready_replicas": status.get("readyReplicas"),
        "available_replicas": status.get("availableReplicas"),
        "unavailable_replicas": status.get("unavailableReplicas"),
        "conditions": status.get("conditions") or [],
        "images": [
            container.get("image")
            for container in template_spec.get("containers") or []
            if container.get("image")
        ],
    }


def _pod_summary(pod: dict[str, Any]) -> dict[str, Any]:
    metadata = pod.get("metadata") or {}
    status = pod.get("status") or {}
    containers = status.get("containerStatuses") or []

    return {
        "name": metadata.get("name"),
        "phase": status.get("phase"),
        "node": (pod.get("spec") or {}).get("nodeName"),
        "ready_containers": sum(1 for item in containers if item.get("ready")),
        "restarts": sum(int(item.get("restartCount") or 0) for item in containers),
        "containers": [_container_status(item) for item in containers],
    }


def _container_status(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": item.get("name"),
        "ready": item.get("ready"),
        "restarts": item.get("restartCount"),
        "state": item.get("state"),
        "last_state": item.get("lastState"),
    }


def _selector_from_deployment(data: dict[str, Any]) -> str | None:
    labels = ((data.get("spec") or {}).get("selector") or {}).get("matchLabels") or {}
    if not labels:
        return None
    return ",".join(f"{key}={value}" for key, value in sorted(labels.items()))


def _images(replicaset: dict[str, Any]) -> list[str]:
    template = (replicaset.get("spec") or {}).get("template") or {}
    pod_spec = template.get("spec") or {}
    return [
        container.get("image")
        for container in pod_spec.get("containers") or []
        if container.get("image")
    ]


def _get_json(path: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    result = k8s_get(path)
    if not result.get("ok"):
        return None, result

    try:
        data = json.loads(result.get("output") or "")
    except (TypeError, ValueError):
        return None, failure_result("Kubernetes API returned a non-JSON response.")

    if not isinstance(data, dict):
        return None, failure_result("Kubernetes API returned an unexpected JSON shape.")

    return data, result


def _json_text(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)


def _validate(value: str, field: str, *, subdomain: bool = False) -> str | None:
    limit = 253 if subdomain else 63
    pattern = _DNS_SUBDOMAIN if subdomain else _DNS_LABEL
    if (
        not isinstance(value, str)
        or not value
        or len(value) > limit
        or not pattern.fullmatch(value)
    ):
        allowed = "letters, digits, '-'" + (" and '.'" if subdomain else "")
        return (
            f"Invalid {field}: {value!r}. Use lowercase {allowed}, "
            "starting and ending with a letter or digit."
        )
    return None
