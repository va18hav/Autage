import json
from typing import Dict, Any, Optional, List


def build_plan_prompt(
    raw_alert: Dict[str, Any],
    incident_title: str,
    severity: str,
    summary: str,
    runbooks_available: bool,
) -> str:
    """
    Prompt for LLM call 1.
    Given the raw alert, the LLM decides which kubectl commands to run and with
    what args, and whether the curated runbooks in the DB should be consulted.
    """
    return f"""You are an expert SRE agent. An incident has been triaged and you must now fetch live logs from the Kubernetes cluster.

## Incident Details
- Title: {incident_title}
- Severity: {severity}
- Summary: {summary}
- Raw Alert: {json.dumps(raw_alert, indent=2)}

## Available Tools
You have access to the following kubectl tools. Choose the most relevant ones based on the alert above.

1. get_pod_logs
   - Purpose: Fetch the last N log lines from a running pod
   - Args: namespace (str), pod_name (str), tail (int, default 100)
   - Use when: You need to see what the application is currently printing

2. get_pod_logs_previous
   - Purpose: Fetch logs from the previous (crashed) container instance
   - Args: namespace (str), pod_name (str), tail (int, default 100)
   - Use when: Pod has restarted/crashed — OOMKill, CrashLoopBackOff

3. get_pod_status
   - Purpose: Get full JSON status of a pod — phase, conditions, container states
   - Args: namespace (str), pod_name (str)
   - Use when: You need to know the pod's current state and conditions

4. describe_pod
   - Purpose: Human-readable pod description — restarts, probe failures, resource limits, events
   - Args: namespace (str), pod_name (str)
   - Use when: You need detailed diagnostics about why a pod is unhealthy

5. get_events
   - Purpose: Recent namespace-level events — evictions, image pull errors, scheduling failures
   - Args: namespace (str)
   - Use when: Always useful — run this for every incident

6. list_pods
   - Purpose: List all pods in a namespace with their current status
   - Args: namespace (str)
   - Use when: You need to see which pods exist or if multiple pods are affected

7. get_deployment
   - Purpose: Deployment status — desired vs available replicas, rollout conditions
   - Args: namespace (str), deployment_name (str)
   - Use when: Alert mentions replica count, rolling update, or deployment issues

## Runbooks
{(
"If the operator has saved runbooks, you may request them next by setting runbooks_needed=true.\n"
"- Set runbooks_needed=true only when a curated, human-written remediation procedure would clearly help beyond the "
"raw logs — e.g. the alert references a known failure mode (OOMKill, CrashLoopBackOff, certificate expiry, "
"connection-pool exhaustion) that team runbooks most likely cover.\n"
"- Set runbooks_needed=false when raw cluster/log data alone is enough (pods healthy, alert ambiguous, or nothing "
"a documented procedure would add)."
)
if runbooks_available
else (
"No runbooks are saved in the database. You MUST set runbooks_needed=false — the value is ignored and no runbook "
"step will run."
)}

## Instructions
- Extract the namespace, pod_name, and any other identifiers from the raw alert
- Select only the tools that are relevant to this specific incident
- Always include get_events — it gives cluster-wide context
- For memory/crash issues, include get_pod_logs_previous
- pod_name and deployment_name should only be set when the tool requires them
"""


def build_summary_prompt(incident_title: str, severity: str, summary: str, logs: Dict[str, Any]) -> str:
    """
    Prompt for LLM call 2.
    Given all raw kubectl outputs, the LLM produces a plain-text log summary.
    """
    logs_text = ""
    for tool_name, result in logs.items():
        status = "SUCCESS" if result.get("ok") else "FAILED"
        output = result.get("output") or result.get("error") or "No output"
        logs_text += f"\n--- {tool_name} [{status}] ---\n{output}\n"

    return f"""You are an expert SRE. You have fetched live data from a Kubernetes cluster about an active incident.
Analyze the data below and summarize the diagnostic findings.

## Incident
- Title: {incident_title}
- Severity: {severity}
- Summary: {summary}

## Live Cluster Data
{logs_text}

## Instructions
- Write a concise plain-text summary (a short paragraph or two)
- Identify which pods are affected and form a hypothesis for the most likely root cause
- Reference the strongest evidence — actual pod names, error messages, statuses, and numbers
- Do not use markdown headings or bullet lists
"""


def build_runbook_selection_prompt(
    incident_title: str,
    severity: str,
    summary: str,
    logs_summary: str,
    runbooks: List[Dict[str, Any]],
) -> str:
    """
    Prompt for the refer_runbooks node, LLM call 1:
    pick which runbook sections to pull from the inventory.
    """
    inventory_lines = []
    for rb in runbooks:
        service = rb.get("service") or "-"
        inventory_lines.append(f"### Runbook: \"{rb['runbook_title']}\" (service: {service})")
        for sec in rb["sections"]:
            inventory_lines.append(f"  - [{sec['order_index']}] {sec['heading']}")
        if not rb["sections"]:
            inventory_lines.append("  - (no sections)")

    return f"""You are an expert SRE agent. You are resolving an active incident and a curated set of runbooks is available.

## Incident
- Title: {incident_title}
- Severity: {severity}
- Summary: {summary}

## Diagnostics so far (k8s logs summary)
{logs_summary}

## Available Runbooks (titles and section headings only)
{chr(10).join(inventory_lines)}

## Instructions
- From the section headings above, select every section likely to contain the exact remediation procedure for this incident
- Reference a section as (runbook_title, section_order_index) — the order_index in square brackets is what you pass back
- If none of the sections are relevant, return an empty selection
"""


def build_recommended_steps_prompt(
    incident_title: str,
    severity: str,
    summary: str,
    logs_summary: str,
    runbooks_summary: str,
) -> str:
    """
    Prompt for the final recommended_steps node — takes the entire state.
    """
    return f"""You are the final step of an SRE agent pipeline: everything has been gathered and you must produce the concrete recommended steps for the on-call engineer.

## Incident
- Title: {incident_title}
- Severity: {severity}
- Triage Summary: {summary}

## Kubernetes Logs Summary
{logs_summary}

## Runbook Findings
{runbooks_summary or "No runbooks were consulted for this incident."}

## Instructions
- Produce a numbered list of concrete, ordered remediation steps
- Prefer the verified runbook procedure when runbook findings are relevant; adapt it to the actual pod/namespace/deployment names from the logs summary
- Each step must state exactly what to run or check — reference real resource names, values, and commands where possible
- Cover immediate mitigation first, then verification that service is restored, then follow-up hardening
- Keep every step actionable on its own (no meta commentary)
"""
