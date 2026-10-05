import sys
from pathlib import Path

# Add project root to sys.path so it works directly from CLI
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import time
import urllib.request
import urllib.error

from services.config import settings
from services.http.verify_webhook import compute_hmac_signature


def send_alert():
    # Append timestamp to pod name so fingerprint is unique each run
    timestamp = int(time.time())
    unique_pod = f"auth-service-7d84b8f58b-{timestamp % 10000}"

    mock_alert = {
        "source": "datadog",
        "metric": "container.memory.usage",
        "threshold": 0.95,
        "current_value": 0.99,
        "pod_name": unique_pod,
        "namespace": "production",
        "restarts_last_hour": 5,
        "cluster": "k8s-prod-us-east-1",
        "timestamp": timestamp,
        "message": f"Pod {unique_pod} is using 99% memory and has crashed 5 times in the last hour.",
    }

    payload_bytes = json.dumps(mock_alert, sort_keys=True).encode("utf-8")
    signature = compute_hmac_signature(payload_bytes, settings.WEBHOOK_SECRET)

    url = "http://localhost:8000/webhooks/alert"
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": f"sha256={signature}",
    }

    print("--> Triggering simulated SRE alert to Autage Webhook...")
    print(f"    Target Pod:  {unique_pod}")
    print(f"    Webhook URL: {url}")

    req = urllib.request.Request(url, data=payload_bytes, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req) as resp:
            status_code = resp.getcode()
            response_body = json.loads(resp.read().decode("utf-8"))

            incident_id = response_body.get("incident_id")
            incident_status = response_body.get("status")

            print("\n[OK] Webhook Accepted by Autage!")
            print(f"     Status Code: {status_code}")
            print(f"     Incident ID: {incident_id}")
            print(f"     Status:      {incident_status}")
            print("\n--> Watch this incident triage live:")
            print(f"     1. In Dashboard: Visit /incidents/{incident_id}")
            print(f"     2. In Terminal Stream: curl -N http://localhost:8000/incidents/{incident_id}/stream\n")

    except urllib.error.HTTPError as e:
        error_content = e.read().decode("utf-8")
        print(f"\n[ERROR] HTTP Error {e.code}: {error_content}")
    except urllib.error.URLError as e:
        print(f"\n[ERROR] Connection Error: Could not connect to {url}.")
        print("        Make sure the FastAPI server is running with:")
        print("        uv run uvicorn services.http.app:app --host 0.0.0.0 --port 8000 --reload")


if __name__ == "__main__":
    send_alert()
