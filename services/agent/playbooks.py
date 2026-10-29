"""Fixed evidence checklists for supported incident types.

The model may identify the incident type, but it never decides which tools to
run. Each playbook below defines the small, predictable set of read-only
evidence that Autage collects before producing a diagnosis.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class IncidentType(str, Enum):
    CRASH_LOOP = "crash_loop"
    BAD_DEPLOYMENT = "bad_deployment"
    OTHER = "other"


class EvidenceTool(str, Enum):
    POD_STATUS = "get_pod_status"
    POD_LOGS = "get_pod_logs"
    POD_PREVIOUS_LOGS = "get_pod_logs_previous"
    DEPLOYMENT = "get_deployment"
    DEPLOYMENT_PODS = "list_deployment_pods"
    DEPLOYMENT_HISTORY = "get_deployment_history"
    EVENTS = "get_events"


class EvidenceScope(str, Enum):
    NAMESPACE = "namespace"
    POD = "pod"
    DEPLOYMENT = "deployment"


@dataclass(frozen=True, slots=True)
class EvidenceStep:
    tool: EvidenceTool
    scope: EvidenceScope
    purpose: str
    required: bool = True


@dataclass(frozen=True, slots=True)
class Playbook:
    incident_type: IncidentType
    title: str
    summary: str
    steps: tuple[EvidenceStep, ...]


CRASH_LOOP_PLAYBOOK = Playbook(
    incident_type=IncidentType.CRASH_LOOP,
    title="CrashLoopBackOff / OOMKilled",
    summary=(
        "Confirm why the container is restarting, identify the affected "
        "workload, and check whether a recent change or memory limit is involved."
    ),
    steps=(
        EvidenceStep(
            tool=EvidenceTool.DEPLOYMENT_PODS,
            scope=EvidenceScope.DEPLOYMENT,
            purpose="Find the pods that belong to the affected deployment.",
            required=False,
        ),
        EvidenceStep(
            tool=EvidenceTool.POD_STATUS,
            scope=EvidenceScope.POD,
            purpose="Read restart count, container state, and termination reason.",
        ),
        EvidenceStep(
            tool=EvidenceTool.POD_PREVIOUS_LOGS,
            scope=EvidenceScope.POD,
            purpose="Read logs from the container instance that crashed.",
            required=False,
        ),
        EvidenceStep(
            tool=EvidenceTool.POD_LOGS,
            scope=EvidenceScope.POD,
            purpose="Read the current container logs if it is running again.",
        ),
        EvidenceStep(
            tool=EvidenceTool.DEPLOYMENT,
            scope=EvidenceScope.DEPLOYMENT,
            purpose="Check desired versus available replicas and rollout state.",
            required=False,
        ),
        EvidenceStep(
            tool=EvidenceTool.EVENTS,
            scope=EvidenceScope.NAMESPACE,
            purpose="Find OOMKills, probe failures, image pull errors, and evictions.",
        ),
    ),
)


BAD_DEPLOYMENT_PLAYBOOK = Playbook(
    incident_type=IncidentType.BAD_DEPLOYMENT,
    title="Bad deployment",
    summary=(
        "Confirm that a rollout is unhealthy, identify the bad revision, and "
        "collect logs from one affected pod."
    ),
    steps=(
        EvidenceStep(
            tool=EvidenceTool.DEPLOYMENT,
            scope=EvidenceScope.DEPLOYMENT,
            purpose="Check desired versus available replicas and rollout conditions.",
        ),
        EvidenceStep(
            tool=EvidenceTool.DEPLOYMENT_HISTORY,
            scope=EvidenceScope.DEPLOYMENT,
            purpose="Identify the current and previous deployment revisions.",
        ),
        EvidenceStep(
            tool=EvidenceTool.DEPLOYMENT_PODS,
            scope=EvidenceScope.DEPLOYMENT,
            purpose="Find healthy and unhealthy pods for the deployment.",
        ),
        EvidenceStep(
            tool=EvidenceTool.POD_LOGS,
            scope=EvidenceScope.POD,
            purpose="Read logs from one affected pod.",
            required=False,
        ),
        EvidenceStep(
            tool=EvidenceTool.EVENTS,
            scope=EvidenceScope.NAMESPACE,
            purpose="Find rollout, probe, scheduling, and image errors.",
        ),
    ),
)


PLAYBOOKS: dict[IncidentType, Playbook] = {
    IncidentType.CRASH_LOOP: CRASH_LOOP_PLAYBOOK,
    IncidentType.BAD_DEPLOYMENT: BAD_DEPLOYMENT_PLAYBOOK,
}

SUPPORTED_INCIDENT_TYPES: tuple[IncidentType, ...] = tuple(PLAYBOOKS)


def get_playbook(incident_type: IncidentType | str | None) -> Optional[Playbook]:
    """Return the fixed playbook for an incident type, if one is supported."""
    if incident_type is None:
        return None

    try:
        parsed_type = IncidentType(incident_type)
    except ValueError:
        return None

    return PLAYBOOKS.get(parsed_type)
