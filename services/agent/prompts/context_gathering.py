import json
from typing import Dict, Any


def build_plan_prompt(raw_alert: Dict[str, Any], incident_title: str, severity: str, summary: str) -> str:
    """
    Prompt for LLM call 1.
    Given the raw alert, the LLM decides which kubectl commands to run and with what args.
    """
    return f"""You are an expert SRE agent. An incident has been triaged and you must now gather live context from the Kubernetes cluster.

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

## Instructions
- Extract the namespace, pod_name, and any other identifiers from the raw alert
- Select only the tools that are relevant to this specific incident
- Always include get_events — it gives cluster-wide context
- For memory/crash issues, include get_pod_logs_previous
- pod_name and deployment_name should only be set when the tool requires them
"""


def build_summary_prompt(incident_title: str, severity: str, summary: str, context: Dict[str, Any]) -> str:
    """
    Prompt for LLM call 2.
    Given all raw kubectl outputs, the LLM produces a structured context summary.
    """
    context_text = ""
    for tool_name, result in context.items():
        status = "SUCCESS" if result.get("ok") else "FAILED"
        output = result.get("output") or result.get("error") or "No output"
        context_text += f"\n--- {tool_name} [{status}] ---\n{output}\n"

    return f"""You are an expert SRE. You have gathered live data from a Kubernetes cluster about an active incident.
Analyze the data below and extract the key diagnostic signals.

## Incident
- Title: {incident_title}
- Severity: {severity}
- Summary: {summary}

## Live Cluster Data
{context_text}

## Instructions
- Identify which pods are affected
- Form a hypothesis for the most likely root cause based on the evidence
- List the 3-5 most important signals you observed
- Suggest the next concrete diagnostic or remediation steps
- Be specific — reference actual pod names, error messages, and numbers from the data above
"""
