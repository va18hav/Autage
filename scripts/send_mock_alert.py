import sys
from pathlib import Path

# Add project root to sys.path so it works directly from CLI
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import argparse
import json
import subprocess
import time
import urllib.request
import urllib.error

from services.http.routes.settings import WEBHOOK_SECRET_PURPOSE
from services.http.verify_webhook import compute_hmac_signature
from services.secrets.store import SecretStore


async def _get_active_secret() -> str:
    try:
        payload = await SecretStore.fetch_payload(WEBHOOK_SECRET_PURPOSE)
    except Exception as exc:
        raise RuntimeError(
            "Could not read the webhook secret from the database. "
            "Check the database configuration and try again."
        ) from exc

    if payload and payload.get("secret"):
        return str(payload["secret"])

    raise RuntimeError(
        "No webhook secret is configured. Open Settings → Integrations and "
        "generate a webhook secret before sending an alert."
    )


def _pick_live_pod(namespace: str, deployment: str) -> str | None:
    """Ask the real cluster for a live pod name so alerts reference something
    that actually exists. Prefers a pod of the given deployment that is
    crashing/restarting (that's the victim Autage should diagnose)."""
    try:
        raw = subprocess.run(
            ["kubectl", "get", "pods", "-n", namespace, "-o", "json"],
            capture_output=True, text=True, timeout=15, check=True,
        ).stdout
    except Exception as exc:
        print(f"    (live pod lookup failed: {exc.__class__.__name__} — falling back to a synthetic name)")
        return None

    try:
        pods = json.loads(raw).get("items", [])
    except ValueError:
        return None

    candidates = [
        p for p in pods
        if deployment in "".join(str(v) for v in (p["metadata"]["labels"] or {}).values())
        or deployment in p["metadata"].get("name", "")
    ] or pods
    if not candidates:
        return None

    def restarts(p: dict) -> int:
        return sum(cs.get("restartCount", 0) for cs in
                   p.get("status", {}).get("containerStatuses", []) or [{}])

    victim = max(candidates, key=restarts)
    return victim["metadata"]["name"]


def send_alert(live: bool = False, namespace: str = "production",
               deployment: str = "auth-service"):
    active_secret = asyncio.run(_get_active_secret())

    timestamp = int(time.time())
    if live:
        real_pod = _pick_live_pod(namespace, deployment)
        if real_pod:
            print(f"    Targeting LIVE pod from cluster: {real_pod}")
            pod_name, restarts = real_pod, None
            try:
                raw = subprocess.run(
                    ["kubectl", "get", "pod", pod_name, "-n", namespace, "-o", "json"],
                    capture_output=True, text=True, timeout=15, check=True).stdout
                pod = json.loads(raw)
                restarts = sum(cs.get("restartCount", 0) for cs in pod["status"].get("containerStatuses", []))
            except Exception:
                pass
        else:
            print("    No live pod found — falling back to a synthetic name.")
            live = False

    if not live:
        # Append timestamp to pod name so fingerprint is unique each run
        restarts = 5
        pod_name = f"{deployment}-7d84b8f58b-{timestamp % 10000}"

    reason = (
        f"Pod {pod_name} is using 99% memory and has crashed"
        + (f" {restarts} times in the last hour." if restarts else "; it is crash-looping right now.")
    )
    mock_alert = {
        "source": "datadog",
        "metric": "container.memory.usage",
        "threshold": 0.95,
        "current_value": 0.99,
        "pod_name": pod_name,
        "namespace": namespace,
        "restarts_last_hour": restarts or 0,
        "cluster": "k8s-prod-us-east-1",
        "timestamp": timestamp,
        "message": reason,
    }

    payload_bytes = json.dumps(mock_alert, sort_keys=True).encode("utf-8")
    signature = compute_hmac_signature(payload_bytes, active_secret)

    url = "http://localhost:8000/webhooks/alert"
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": f"sha256={signature}",
    }

    print("--> Triggering simulated SRE alert to Autage Webhook...")
    print(f"    Target Pod:  {pod_name}")
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
    parser = argparse.ArgumentParser(description="Send a (optionally live) alert to the Autage webhook.")
    parser.add_argument("--live", action="store_true",
                        help="pick a real pod name from the cluster via kubectl (falls back to a synthetic name)")
    parser.add_argument("--namespace", default="production",
                        help="namespace to target (default: production)")
    parser.add_argument("--deployment", default="auth-service",
                        help="deployment/pod prefix to look for (default: auth-service)")
    args = parser.parse_args()
    send_alert(live=args.live, namespace=args.namespace, deployment=args.deployment)
