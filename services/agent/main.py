from dotenv import load_dotenv
load_dotenv()

from services.agent.graph import builder
import json

graph = builder.compile()

if __name__ == "__main__":
    mock_alert = {
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

    print("--- Running SRE Agent Graph ---")
    result = graph.invoke(mock_alert)
    print("\n--- Final Graph State ---")
    print(json.dumps(result, indent=2))