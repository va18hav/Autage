import json
from typing import TypedDict, Dict, Any

def build_system_prompt(raw_alert: Dict[str, Any]) -> str:
    return f"""You are an expert SRE on-call engineer triaging an incoming alert.
Analyze the incident details below:
- Raw Alert Data: {json.dumps(raw_alert, indent=2)}
Task:
1. Determine the severity level: "P1" (critical/outage), "P2" (major/degraded), or "P3" (minor/info).
2. Provide a concise 2-3 sentence summary of the incident and potential impact.
Output Requirement:
You must respond with ONLY valid JSON (no markdown formatting, no backticks, no extra text).
JSON format:
{{
  "incident_title": "suitable title for the incident",
  "description": "description of the incident"  
  "severity": "<P1 | P2 | P3>",
  "summary": "<concise summary>"
}}"""