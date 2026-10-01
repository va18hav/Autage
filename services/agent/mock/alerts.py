# Mock alert data — moved from main.py
# Scenario: auth-service pod is OOMKilling repeatedly in production

MOCK_INCIDENT = {
    "incident_id": "INC-1042",
    "raw_alert": {
        "source": "datadog",
        "metric": "container.memory.usage",
        "threshold": 0.95,
        "current_value": 0.99,
        "pod_name": "auth-service-7d84b8f58b-xyz",
        "namespace": "production",
        "restarts_last_hour": 4,
        "cluster": "k8s-prod-us-east-1"
    }
}
