"""Investigate an incident with an LLM that chooses read-only tools.

The model receives the incident facts, the initial runbook guidance, and the
tool schemas. It can inspect Kubernetes resources and request additional
runbook searches. This node executes those calls, records Kubernetes results as
evidence, merges runbook notes, and never lets the model perform writes.
"""

import asyncio
import json
from typing import Any, Dict, List, Optional, Set, Tuple

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from services.agent.llm import StepKey, get_llm
from services.agent.nodes.trace_step import traced_step
from services.agent.prompts.investigate import (
    build_investigation_system_prompt,
    build_investigation_user_prompt,
)
from services.agent.state import AgentState, EvidenceRecord
from services.agent.tools.k8s import (
    get_deployment,
    get_deployment_history,
    get_events,
    get_pod_logs,
    get_pod_logs_previous,
    get_pod_status,
    list_deployment_pods,
)
from services.agent.tools.k8s_runtime import (
    failure_result,
    reset_cluster_credentials,
    set_cluster_credentials,
)
from services.agent.tools.runbooks import (
    fetch_runbook_sections,
    format_runbook_catalog,
    format_runbook_sections,
    load_runbook_catalog,
)
from services.secrets.store import SecretStore

_KUBERNETES_PURPOSE = "kubernetes"
_MAX_TOOL_ROUNDS = 5
_MAX_TOOL_CALLS = 8
_RUNBOOK_SEARCH_TOOL = "search_runbooks"
_RUNBOOK_FETCH_TOOL = "read_runbook_sections"
_RUNBOOK_TOOLS = {_RUNBOOK_SEARCH_TOOL, _RUNBOOK_FETCH_TOOL}

_POD_TOOLS = {"get_pod_status", "get_pod_logs", "get_pod_logs_previous"}
_POD_LOG_TOOLS = {"get_pod_logs", "get_pod_logs_previous"}
_DEPLOYMENT_TOOLS = {
    "get_deployment",
    "list_deployment_pods",
    "get_deployment_history",
}
_TOOL_SCOPES = {
    "get_pod_status": "pod",
    "get_pod_logs": "pod",
    "get_pod_logs_previous": "pod",
    "get_deployment": "deployment",
    "list_deployment_pods": "deployment",
    "get_deployment_history": "deployment",
    "get_events": "namespace",
}


@tool("get_pod_status")
def get_pod_status_tool(namespace: str, pod_name: str) -> str:
    """Read one pod's phase, container states, restart counts, and conditions.
    Use this before logs when a pod is crashing, restarting, or not ready."""
    return _result_json(get_pod_status(namespace, pod_name))


@tool("get_pod_logs")
def get_pod_logs_tool(
    namespace: str,
    pod_name: str,
    tail: int = 200,
    container: str | None = None,
) -> str:
    """Read the current logs for one pod. Use after checking pod status.
    Set `container` when the pod has more than one container."""
    return _result_json(
        get_pod_logs(
            namespace,
            pod_name,
            tail=tail,
            container=container,
        )
    )


@tool("get_pod_logs_previous")
def get_pod_logs_previous_tool(
    namespace: str,
    pod_name: str,
    tail: int = 200,
    container: str | None = None,
) -> str:
    """Read logs from the previous container instance that crashed.
    Use for CrashLoopBackOff, OOMKilled, or repeated restarts."""
    return _result_json(
        get_pod_logs_previous(
            namespace,
            pod_name,
            tail=tail,
            container=container,
        )
    )


@tool("get_deployment")
def get_deployment_tool(namespace: str, deployment_name: str) -> str:
    """Read a deployment's desired, ready, and available replicas, rollout
    conditions, generation, and container images."""
    return _result_json(get_deployment(namespace, deployment_name))


@tool("list_deployment_pods")
def list_deployment_pods_tool(namespace: str, deployment_name: str) -> str:
    """List the pods selected by a deployment, including readiness and restart
    counts. Use this to discover pod names when only a deployment is known."""
    return _result_json(list_deployment_pods(namespace, deployment_name))


@tool("get_deployment_history")
def get_deployment_history_tool(namespace: str, deployment_name: str) -> str:
    """Read deployment revisions from its ReplicaSets, including images and
    replica counts. Use when a recent rollout or bad revision is suspected."""
    return _result_json(get_deployment_history(namespace, deployment_name))


@tool("get_events")
def get_events_tool(namespace: str) -> str:
    """Read recent Warning events in a namespace, such as OOMKilling,
    FailedScheduling, Unhealthy, FailedPull, and Evicted events."""
    return _result_json(get_events(namespace))


@tool("search_runbooks")
async def search_runbooks_tool(
    query: str = "",
    service: str | None = None,
    incident_type: str | None = None,
) -> str:
    """List runbook titles and section headings that may be relevant. This
    returns an index only, not section content. Use it when the initial
    runbook guidance is insufficient, then call `read_runbook_sections` for
    the specific sections you choose."""
    try:
        catalog = await load_runbook_catalog(
            service=service,
            incident_type=incident_type or "other",
            query=query or None,
        )
    except Exception as exc:
        return _result_json(failure_result(f"Runbook search failed: {exc}"))

    return _result_json(
        {
            "ok": True,
            "output": (
                format_runbook_catalog(catalog)
                if catalog
                else "No matching runbooks were found."
            ),
            "error": None,
            "truncated": False,
            "runbook_count": len(catalog),
        }
    )


@tool("read_runbook_sections")
async def read_runbook_sections_tool(
    runbook_id: str,
    section_indexes: list[int],
) -> str:
    """Read chosen sections from a runbook. Use only a runbook_id and section
    indexes returned in the runbook catalog. Read at most three sections per
    call and only what is needed for this incident."""
    try:
        result = await fetch_runbook_sections(
            runbook_id,
            section_indexes,
        )
    except Exception as exc:
        return _result_json(
            failure_result(f"Runbook section read failed: {exc}")
        )
    return _result_json(result)


TOOLS = [
    get_pod_status_tool,
    get_pod_logs_tool,
    get_pod_logs_previous_tool,
    get_deployment_tool,
    list_deployment_pods_tool,
    get_deployment_history_tool,
    get_events_tool,
    search_runbooks_tool,
    read_runbook_sections_tool,
]
TOOLS_BY_NAME = {item.name: item for item in TOOLS}


@traced_step("investigate")
async def investigate(state: AgentState) -> Dict[str, Any]:
    """Ask the model which read-only tools to run, then record the results."""
    namespace = state.get("namespace")
    pod_name = state.get("pod_name")
    deployment_name = state.get("deployment_name")
    container_name = state.get("container_name")
    incident_type = _text(state.get("incident_type"), "other")
    runbooks_summary = state.get("runbooks_summary") or ""

    if not namespace:
        return {
            "evidence": [],
            "missing_evidence": [
                "Namespace was not provided, so Kubernetes evidence could not be "
                "collected."
            ],
            "pod_name": pod_name,
            "deployment_name": deployment_name,
            "container_name": container_name,
            "runbooks_summary": runbooks_summary,
        }

    credentials = await SecretStore.fetch_payload(_KUBERNETES_PURPOSE)
    if not isinstance(credentials, dict):
        return {
            "evidence": [],
            "missing_evidence": ["Kubernetes cluster is not configured."],
            "pod_name": pod_name,
            "deployment_name": deployment_name,
            "container_name": container_name,
            "runbooks_summary": runbooks_summary,
        }

    messages = [
        SystemMessage(content=build_investigation_system_prompt(_MAX_TOOL_CALLS)),
        HumanMessage(
            content=build_investigation_user_prompt(
                incident_title=state.get("incident_title") or "Untitled incident",
                incident_type=incident_type,
                severity=_text(state.get("severity"), "unknown"),
                summary=state.get("summary") or "",
                description=state.get("description") or "",
                namespace=namespace,
                pod_name=pod_name,
                deployment_name=deployment_name,
                container_name=container_name,
                runbooks_summary=runbooks_summary,
                raw_alert=state.get("raw_alert") or {},
            )
        ),
    ]

    llm = get_llm(StepKey.INVESTIGATE)
    model = llm.bind_tools(TOOLS)

    evidence: List[EvidenceRecord] = []
    missing: List[str] = []
    runbook_notes: List[str] = [runbooks_summary]
    tool_calls = 0
    budget_hit = False

    token = set_cluster_credentials(credentials)
    try:
        for _round in range(_MAX_TOOL_ROUNDS):
            response = await model.ainvoke(messages)
            messages.append(response)

            calls = getattr(response, "tool_calls", None) or []
            if not calls:
                break

            for call in calls:
                if not isinstance(call, dict):
                    continue
                if tool_calls >= _MAX_TOOL_CALLS:
                    _add_missing(
                        missing,
                        f"Investigation stopped after {_MAX_TOOL_CALLS} "
                        "tool calls.",
                    )
                    budget_hit = True
                    break

                name = str(call.get("name") or "")
                raw_args = call.get("args") or {}
                args = raw_args if isinstance(raw_args, dict) else {}
                args = _fill_args(
                    name,
                    args,
                    namespace,
                    pod_name,
                    deployment_name,
                    container_name,
                    incident_type,
                )

                result = await _execute_tool(name, args)
                tool_calls += 1

                if name in _RUNBOOK_TOOLS:
                    if name == _RUNBOOK_FETCH_TOOL:
                        _merge_runbook_result(runbook_notes, result)
                    if not result.get("ok"):
                        label = (
                            "Runbook search failed"
                            if name == _RUNBOOK_SEARCH_TOOL
                            else "Runbook section read failed"
                        )
                        _add_missing(
                            missing,
                            f"{label}: "
                            f"{result.get('error') or 'unknown error'}",
                        )
                else:
                    evidence.append(_record(name, args, result))
                    (
                        pod_name,
                        deployment_name,
                        container_name,
                    ) = _update_targets(
                        name,
                        args,
                        result,
                        pod_name,
                        deployment_name,
                        container_name,
                    )

                messages.append(
                    ToolMessage(
                        content=json.dumps(result, default=str),
                        tool_call_id=str(call.get("id") or f"call-{tool_calls}"),
                    )
                )

            if budget_hit:
                break
        else:
            _add_missing(
                missing,
                f"Investigation stopped after {_MAX_TOOL_ROUNDS} model turns.",
            )
    finally:
        reset_cluster_credentials(token)

    _add_unresolved_failures(missing, evidence)

    if not evidence:
        _add_missing(
            missing,
            "The model did not request any Kubernetes evidence tools.",
        )

    return {
        "evidence": evidence,
        "missing_evidence": missing,
        "pod_name": pod_name,
        "deployment_name": deployment_name,
        "container_name": container_name,
        "runbooks_summary": _join_runbook_notes(runbook_notes),
    }


async def _execute_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Run one tool, keeping async DB tools on the main event loop."""
    tool_obj = TOOLS_BY_NAME.get(name)
    if tool_obj is None:
        return failure_result(f"Unknown investigation tool: {name}")

    func = getattr(tool_obj, "func", None)
    coroutine = getattr(tool_obj, "coroutine", None)

    try:
        if callable(coroutine):
            raw = await coroutine(**args)
        elif callable(func):
            raw = await asyncio.to_thread(func, **args)
        else:
            return failure_result(
                f"Investigation tool cannot run locally: {name}"
            )
    except Exception as exc:  # invalid arguments, network errors, etc.
        return failure_result(f"Tool call failed: {exc}")

    if isinstance(raw, dict):
        return raw

    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return failure_result("Investigation tool returned an invalid result.")

    if not isinstance(parsed, dict):
        return failure_result("Investigation tool returned an invalid result.")
    return parsed


def _fill_args(
    name: str,
    args: Dict[str, Any],
    namespace: str,
    pod_name: Optional[str],
    deployment_name: Optional[str],
    container_name: Optional[str],
    incident_type: str,
) -> Dict[str, Any]:
    """Fill known targets only when the model omitted them."""
    filled = dict(args)

    if name == _RUNBOOK_SEARCH_TOOL:
        if deployment_name and not filled.get("service"):
            filled["service"] = deployment_name
        if incident_type and not filled.get("incident_type"):
            filled["incident_type"] = incident_type
        return filled

    if name == _RUNBOOK_FETCH_TOOL:
        return filled

    if not filled.get("namespace"):
        filled["namespace"] = namespace
    if name in _POD_TOOLS and pod_name and not filled.get("pod_name"):
        filled["pod_name"] = pod_name
    if (
        name in _DEPLOYMENT_TOOLS
        and deployment_name
        and not filled.get("deployment_name")
    ):
        filled["deployment_name"] = deployment_name
    if (
        name in _POD_LOG_TOOLS
        and container_name
        and not filled.get("container")
    ):
        filled["container"] = container_name

    return filled


def _merge_runbook_result(
    notes: List[str], result: Dict[str, Any]
) -> None:
    """Keep fetched runbook sections without duplicating the initial set."""
    if not result.get("ok") or not result.get("runbook_id"):
        return

    sections = result.get("sections") or []
    if not sections:
        return

    output = format_runbook_sections(
        result.get("title") or "Untitled runbook",
        result.get("service"),
        sections,
    )
    if output and output not in notes:
        notes.append(output)


def _join_runbook_notes(notes: List[str]) -> str:
    return "\n\n".join(
        note.strip() for note in notes if note and note.strip()
    )


def _update_targets(
    name: str,
    args: Dict[str, Any],
    result: Dict[str, Any],
    pod_name: Optional[str],
    deployment_name: Optional[str],
    container_name: Optional[str],
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    if not result.get("ok"):
        return pod_name, deployment_name, container_name

    if not pod_name and isinstance(args.get("pod_name"), str):
        pod_name = args["pod_name"]
    if not deployment_name and isinstance(args.get("deployment_name"), str):
        deployment_name = args["deployment_name"]
    if not container_name and isinstance(args.get("container"), str):
        container_name = args["container"]

    if name == "list_deployment_pods" and not pod_name:
        pod_name = _pick_pod(result)
    elif name == "get_pod_status" and not container_name:
        container_name = _pick_container(result)

    return pod_name, deployment_name, container_name


def _record(
    name: str, args: Dict[str, Any], result: Dict[str, Any]
) -> EvidenceRecord:
    if not isinstance(result, dict):
        result = failure_result("The evidence tool returned an invalid result.")

    error = result.get("error")
    return {
        "tool": name,
        "scope": _TOOL_SCOPES.get(name, "unknown"),
        "target": _target(name, args),
        "ok": bool(result.get("ok")),
        "output": str(result.get("output") or ""),
        "error": str(error) if error is not None else None,
        "truncated": bool(result.get("truncated")),
    }


def _target(name: str, args: Dict[str, Any]) -> str:
    namespace = str(args.get("namespace") or "").strip()

    if name in _POD_TOOLS:
        pod_name = str(args.get("pod_name") or "").strip()
        return (
            f"{namespace}/{pod_name}".strip("/")
            if pod_name
            else namespace or "unknown"
        )
    if name in _DEPLOYMENT_TOOLS:
        deployment_name = str(args.get("deployment_name") or "").strip()
        return (
            f"{namespace}/{deployment_name}".strip("/")
            if deployment_name
            else namespace or "unknown"
        )
    return namespace or "unknown"


def _add_unresolved_failures(
    missing: List[str], evidence: List[EvidenceRecord]
) -> None:
    succeeded: Set[str] = {item["tool"] for item in evidence if item["ok"]}
    for item in evidence:
        if item["ok"] or item["tool"] in succeeded:
            continue
        _add_missing(
            missing,
            f"{item['tool']} failed for {item['target']}: "
            f"{item['error'] or 'unknown error'}",
        )


def _pick_pod(result: Dict[str, Any]) -> Optional[str]:
    data = _parse_json(result)
    if not data:
        return None

    candidates = []
    for item in data.get("pods") or data.get("items") or []:
        if not isinstance(item, dict):
            continue

        metadata = item.get("metadata") or {}
        name = item.get("name") or metadata.get("name")
        if not name:
            continue

        ready = item.get("ready_containers")
        if ready is None:
            ready = item.get("ready")
        restarts = item.get("restarts")
        if restarts is None:
            restarts = _raw_restarts(item)

        candidates.append((int(restarts or 0), -int(ready or 0), name))

    if not candidates:
        return None

    candidates.sort(reverse=True)
    return candidates[0][2]


def _pick_container(result: Dict[str, Any]) -> Optional[str]:
    data = _parse_json(result)
    if not data:
        return None

    containers = data.get("containers")
    if not containers:
        containers = (data.get("status") or {}).get("containerStatuses") or []

    candidates = []
    for item in containers:
        if not isinstance(item, dict):
            continue

        name = item.get("name")
        if not name:
            continue

        restarts = item.get("restarts")
        if restarts is None:
            restarts = item.get("restartCount")
        candidates.append((0 if item.get("ready") else 1, int(restarts or 0), name))

    if not candidates:
        return None

    candidates.sort(reverse=True)
    return candidates[0][2]


def _raw_restarts(pod: Dict[str, Any]) -> int:
    containers = (pod.get("status") or {}).get("containerStatuses") or []
    return sum(
        int(item.get("restartCount") or 0)
        for item in containers
        if isinstance(item, dict)
    )


def _parse_json(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not result.get("ok"):
        return None
    try:
        data = json.loads(result.get("output") or "")
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _result_json(result: Dict[str, Any]) -> str:
    return json.dumps(result, default=str)


def _text(value: Any, fallback: str) -> str:
    if value is None:
        return fallback
    return str(getattr(value, "value", value) or fallback)


def _add_missing(missing: List[str], message: str) -> None:
    if message not in missing:
        missing.append(message)
