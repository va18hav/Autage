import asyncio
import json
from typing import Any, Dict, List, Optional

from services.agent.nodes.trace_step import traced_step
from services.agent.playbooks import (
    EvidenceScope,
    EvidenceStep,
    EvidenceTool,
    Playbook,
    get_playbook,
)
from services.agent.state import AgentState, EvidenceRecord
from services.agent.tools.kubectl import (
    get_deployment,
    get_deployment_history,
    get_events,
    get_pod_logs,
    get_pod_logs_previous,
    get_pod_status,
    list_deployment_pods,
    reset_cluster_credentials,
    set_cluster_credentials,
)
from services.agent.tools.kubectl_runtime import KubeResult
from services.secrets.store import SecretStore

LOG_TAIL = 200


def _failed_result(message: str) -> KubeResult:
    return {
        "ok": False,
        "output": "",
        "error": message,
        "truncated": False,
    }


def _target_label(
    scope: EvidenceScope,
    namespace: Optional[str],
    pod_name: Optional[str],
    deployment_name: Optional[str],
) -> str:
    if scope == EvidenceScope.NAMESPACE:
        return namespace or "unknown namespace"
    if scope == EvidenceScope.POD:
        if namespace and pod_name:
            return f"{namespace}/{pod_name}"
        return pod_name or "unknown pod"
    if namespace and deployment_name:
        return f"{namespace}/{deployment_name}"
    return deployment_name or "unknown deployment"


def _missing_target(
    step: EvidenceStep,
    namespace: Optional[str],
    pod_name: Optional[str],
    deployment_name: Optional[str],
) -> Optional[str]:
    if not namespace:
        return "namespace is missing from the alert"
    if step.scope == EvidenceScope.POD and not pod_name:
        return "pod name is missing and no pod could be resolved"
    if step.scope == EvidenceScope.DEPLOYMENT and not deployment_name:
        return "deployment name is missing from the alert"
    return None


def _record(
    step: EvidenceStep,
    target: str,
    result: KubeResult,
) -> EvidenceRecord:
    return {
        "tool": step.tool.value,
        "scope": step.scope.value,
        "target": target,
        "ok": bool(result.get("ok")),
        "output": str(result.get("output") or ""),
        "error": result.get("error"),
        "truncated": bool(result.get("truncated")),
    }


def _pick_pod(payload: dict) -> Optional[str]:
    pods = payload.get("pods")
    if not isinstance(pods, list) or not pods:
        return None

    def rank(pod: dict) -> tuple[bool, int]:
        containers = int(pod.get("containers") or 0)
        ready = int(pod.get("ready") or 0)
        restarts = int(pod.get("restarts") or 0)
        return (containers > 0 and ready < containers, restarts)

    selected = max(pods, key=rank)
    name = selected.get("name")
    return str(name) if name else None


def _pick_container(payload: dict) -> Optional[str]:
    statuses = payload.get("status", {}).get("containerStatuses")
    if not isinstance(statuses, list) or not statuses:
        return None

    def rank(container: dict) -> tuple[int, int]:
        state = container.get("state") or {}
        last_state = container.get("lastState") or {}
        if state.get("waiting"):
            priority = 0
        elif last_state.get("terminated"):
            priority = 1
        elif not container.get("ready"):
            priority = 2
        else:
            priority = 3
        return priority, -int(container.get("restartCount") or 0)

    selected = min(statuses, key=rank)
    name = selected.get("name")
    return str(name) if name else None


def _call_tool(
    step: EvidenceStep,
    namespace: Optional[str],
    pod_name: Optional[str],
    deployment_name: Optional[str],
    container_name: Optional[str],
) -> KubeResult:
    if step.tool == EvidenceTool.EVENTS:
        assert namespace is not None
        return get_events(namespace)

    if step.tool == EvidenceTool.DEPLOYMENT:
        assert namespace is not None and deployment_name is not None
        return get_deployment(namespace, deployment_name)

    if step.tool == EvidenceTool.DEPLOYMENT_HISTORY:
        assert namespace is not None and deployment_name is not None
        return get_deployment_history(namespace, deployment_name)

    if step.tool == EvidenceTool.DEPLOYMENT_PODS:
        assert namespace is not None and deployment_name is not None
        return list_deployment_pods(namespace, deployment_name)

    assert namespace is not None and pod_name is not None
    if step.tool == EvidenceTool.POD_STATUS:
        return get_pod_status(namespace, pod_name)
    if step.tool == EvidenceTool.POD_LOGS:
        return get_pod_logs(
            namespace,
            pod_name,
            tail=LOG_TAIL,
            container_name=container_name,
        )
    if step.tool == EvidenceTool.POD_PREVIOUS_LOGS:
        return get_pod_logs_previous(
            namespace,
            pod_name,
            tail=LOG_TAIL,
            container_name=container_name,
        )

    return _failed_result(f"Unknown evidence tool: {step.tool.value}")


def _add_missing(missing: List[str], message: str) -> None:
    if message not in missing:
        missing.append(message)


async def _run_playbook(
    playbook: Playbook,
    namespace: Optional[str],
    pod_name: Optional[str],
    deployment_name: Optional[str],
    container_name: Optional[str],
) -> tuple[List[EvidenceRecord], List[str], Optional[str], Optional[str]]:
    evidence: List[EvidenceRecord] = []
    missing: List[str] = []

    for step in playbook.steps:
        target_missing = _missing_target(
            step,
            namespace,
            pod_name,
            deployment_name,
        )
        if target_missing:
            target = _target_label(
                step.scope,
                namespace,
                pod_name,
                deployment_name,
            )
            evidence.append(
                _record(step, target, _failed_result(target_missing))
            )
            _add_missing(
                missing,
                f"{step.tool.value} was not collected because {target_missing}.",
            )
            continue

        target = _target_label(
            step.scope,
            namespace,
            pod_name,
            deployment_name,
        )

        try:
            result = await asyncio.to_thread(
                _call_tool,
                step,
                namespace,
                pod_name,
                deployment_name,
                container_name,
            )
        except Exception as exc:
            result = _failed_result(f"Evidence collection failed: {exc}")

        evidence.append(_record(step, target, result))

        if not result["ok"]:
            message = result.get("error") or "unknown error"
            _add_missing(
                missing,
                f"{step.tool.value} failed for {target}: {message}.",
            )
            continue

        payload: Optional[dict] = None
        if step.tool in (
            EvidenceTool.POD_STATUS,
            EvidenceTool.DEPLOYMENT_PODS,
        ):
            try:
                payload = json.loads(result["output"])
            except json.JSONDecodeError:
                _add_missing(
                    missing,
                    f"{step.tool.value} returned malformed JSON.",
                )

        if step.tool == EvidenceTool.DEPLOYMENT_PODS and payload:
            resolved_pod = _pick_pod(payload)
            if resolved_pod:
                pod_name = resolved_pod
            else:
                _add_missing(
                    missing,
                    f"No pods were found for deployment {deployment_name}.",
                )

        if step.tool == EvidenceTool.POD_STATUS and payload and not container_name:
            container_name = _pick_container(payload)

    return evidence, missing, pod_name, container_name


@traced_step("collect_evidence")
async def collect_evidence(state: AgentState) -> Dict[str, Any]:
    """Run the fixed evidence checklist for the incident's playbook."""
    playbook = get_playbook(state.get("incident_type"))
    if playbook is None:
        incident_type = state.get("incident_type") or "unknown"
        return {
            "evidence": [],
            "missing_evidence": [
                f"No supported playbook exists for incident type '{incident_type}'."
            ],
        }

    namespace = state.get("namespace")
    pod_name = state.get("pod_name")
    deployment_name = state.get("deployment_name")
    container_name = state.get("container_name")

    credentials = await SecretStore.fetch_payload("kubernetes")
    credentials_token = set_cluster_credentials(credentials)

    try:
        evidence, missing, pod_name, container_name = await _run_playbook(
            playbook=playbook,
            namespace=namespace,
            pod_name=pod_name,
            deployment_name=deployment_name,
            container_name=container_name,
        )
    finally:
        reset_cluster_credentials(credentials_token)

    return {
        "namespace": namespace,
        "pod_name": pod_name,
        "deployment_name": deployment_name,
        "container_name": container_name,
        "evidence": evidence,
        "missing_evidence": missing,
    }
