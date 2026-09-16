"""
Realistic mock responses for every kubectl tool.
These simulate what you'd actually get back from a cluster
running the auth-service OOMKill scenario (INC-1042).

The get_mock_response() function is called by tools/kubectl.py
when the MOCK_KUBECTL=true env var is set.
"""


# ── Individual mock outputs ───────────────────────────────────────────────────

_POD_LOGS = """\
2026-09-30T12:40:01Z INFO  auth-service starting up version=2.4.1
2026-09-30T12:40:02Z INFO  Connected to database pool_size=20
2026-09-30T12:40:15Z INFO  Token validation cache warmed entries=50000
2026-09-30T12:41:03Z INFO  Serving requests port=8080
2026-09-30T12:42:11Z WARN  Heap usage elevated heap_used=820MB heap_limit=950MB
2026-09-30T12:42:45Z WARN  GC pause exceeded threshold pause_ms=1800 threshold_ms=500
2026-09-30T12:43:02Z WARN  Heap usage critical heap_used=910MB heap_limit=950MB
2026-09-30T12:43:10Z ERROR Cache eviction failing — no free memory available
2026-09-30T12:43:18Z ERROR Failed to process token refresh request: out of memory
2026-09-30T12:43:21Z FATAL signal: killed
"""

_POD_LOGS_PREVIOUS = """\
2026-09-30T12:35:00Z INFO  auth-service starting up version=2.4.1
2026-09-30T12:35:01Z INFO  Connected to database pool_size=20
2026-09-30T12:36:44Z WARN  Heap usage elevated heap_used=800MB heap_limit=950MB
2026-09-30T12:37:30Z WARN  Large in-memory session cache detected entries=120000 expected_max=50000
2026-09-30T12:38:12Z WARN  GC pause exceeded threshold pause_ms=2300 threshold_ms=500
2026-09-30T12:38:55Z ERROR Heap dump requested but insufficient memory to write
2026-09-30T12:39:01Z FATAL Out of memory: Kill process 1 (auth-service) score 999 or sacrifice child
Killed
"""

_POD_STATUS_JSON = """\
{
  "apiVersion": "v1",
  "kind": "Pod",
  "metadata": {
    "name": "auth-service-7d84b8f58b-xyz",
    "namespace": "production",
    "labels": { "app": "auth-service" }
  },
  "status": {
    "phase": "Running",
    "conditions": [
      { "type": "Ready", "status": "False", "reason": "ContainersNotReady" }
    ],
    "containerStatuses": [
      {
        "name": "auth-service",
        "ready": false,
        "restartCount": 4,
        "lastState": {
          "terminated": {
            "reason": "OOMKilled",
            "exitCode": 137,
            "finishedAt": "2026-09-30T12:43:21Z"
          }
        },
        "state": {
          "running": {
            "startedAt": "2026-09-30T12:43:35Z"
          }
        }
      }
    ]
  }
}
"""

_DESCRIBE_POD = """\
Name:             auth-service-7d84b8f58b-xyz
Namespace:        production
Node:             ip-10-0-1-45.ec2.internal/10.0.1.45
Start Time:       Tue, 30 Sep 2026 12:40:00 +0000
Labels:           app=auth-service
Status:           Running

Containers:
  auth-service:
    Image:          company/auth-service:2.4.1
    Limits:
      cpu:          500m
      memory:       1Gi
    Requests:
      cpu:          250m
      memory:       512Mi
    Liveness:       http-get http://:8080/healthz delay=30s timeout=5s period=10s
    Readiness:      http-get http://:8080/readyz delay=10s timeout=3s period=5s
    Last State:     Terminated
      Reason:       OOMKilled
      Exit Code:    137
      Started:      Tue, 30 Sep 2026 12:35:00 +0000
      Finished:     Tue, 30 Sep 2026 12:39:01 +0000
    Ready:          False
    Restart Count:  4

Conditions:
  Type              Status
  Initialized       True
  Ready             False
  ContainersReady   False

Events:
  Type     Reason      Age    From     Message
  ----     ------      ---    ----     -------
  Warning  OOMKilling  4m     kubelet  Memory cgroup out of memory: Kill process 1 (auth-service) score 999
  Warning  BackOff     2m     kubelet  Back-off restarting failed container auth-service
  Normal   Pulled      18s    kubelet  Successfully pulled image company/auth-service:2.4.1
  Normal   Started     15s    kubelet  Started container auth-service
"""

_GET_EVENTS = """\
LAST SEEN   TYPE      REASON      OBJECT                                  MESSAGE
4m          Warning   OOMKilling  pod/auth-service-7d84b8f58b-xyz         Memory cgroup out of memory: Kill process 1 (auth-service) score 999 or sacrifice child
3m          Warning   BackOff     pod/auth-service-7d84b8f58b-xyz         Back-off restarting failed container auth-service in pod auth-service-7d84b8f58b-xyz
2m30s       Normal    Killing     pod/auth-service-7d84b8f58b-xyz         Stopping container auth-service
2m15s       Normal    Pulled      pod/auth-service-7d84b8f58b-xyz         Successfully pulled image company/auth-service:2.4.1
2m10s       Normal    Created     pod/auth-service-7d84b8f58b-xyz         Created container auth-service
2m8s        Normal    Started     pod/auth-service-7d84b8f58b-xyz         Started container auth-service
1m          Warning   OOMKilling  pod/auth-service-7d84b8f58b-xyz         Memory cgroup out of memory: Kill process 1 (auth-service) score 999 or sacrifice child
30s         Warning   BackOff     pod/auth-service-7d84b8f58b-xyz         Back-off restarting failed container
"""

_LIST_PODS = """\
NAME                                    READY   STATUS             RESTARTS   AGE
auth-service-7d84b8f58b-xyz             0/1     CrashLoopBackOff   4          18m
payment-service-6c9df7b8d-abc           1/1     Running            0          2d
user-service-5f8bc6c7d-def              1/1     Running            0          2d
notification-service-4d7ab5b6c-ghi      1/1     Running            0          2d
"""

_GET_DEPLOYMENT = """\
{
  "apiVersion": "apps/v1",
  "kind": "Deployment",
  "metadata": {
    "name": "auth-service",
    "namespace": "production"
  },
  "spec": {
    "replicas": 1,
    "strategy": { "type": "RollingUpdate" }
  },
  "status": {
    "replicas": 1,
    "updatedReplicas": 1,
    "readyReplicas": 0,
    "availableReplicas": 0,
    "conditions": [
      {
        "type": "Available",
        "status": "False",
        "reason": "MinimumReplicasUnavailable",
        "message": "Deployment does not have minimum availability."
      },
      {
        "type": "Progressing",
        "status": "True",
        "reason": "ReplicaSetUpdated"
      }
    ]
  }
}
"""


# ── Response router ───────────────────────────────────────────────────────────

def get_mock_response(args: list[str]) -> dict:
    """
    Given the args list that would have been passed to subprocess.run(),
    return a realistic pre-canned kubectl response.

    args examples:
      ["kubectl", "logs",     "auth-service-...", "-n", "production", "--tail=100"]
      ["kubectl", "logs",     "auth-service-...", "-n", "production", "--previous", "--tail=100"]
      ["kubectl", "get",      "pod",  "auth-service-...", "-n", "production", "-o", "json"]
      ["kubectl", "get",      "pods", "-n", "production"]
      ["kubectl", "get",      "events", "-n", "production", "--sort-by=.lastTimestamp"]
      ["kubectl", "get",      "deployment", "auth-service", "-n", "production", "-o", "json"]
      ["kubectl", "describe", "pod",  "auth-service-...", "-n", "production"]
    """
    verb = args[1] if len(args) > 1 else ""
    resource = args[2] if len(args) > 2 else ""

    if verb == "logs":
        if "--previous" in args:
            return {"ok": True, "output": _POD_LOGS_PREVIOUS, "error": None}
        return {"ok": True, "output": _POD_LOGS, "error": None}

    if verb == "get":
        if resource == "pod":
            return {"ok": True, "output": _POD_STATUS_JSON, "error": None}
        if resource == "pods":
            return {"ok": True, "output": _LIST_PODS, "error": None}
        if resource == "events":
            return {"ok": True, "output": _GET_EVENTS, "error": None}
        if resource == "deployment":
            return {"ok": True, "output": _GET_DEPLOYMENT, "error": None}

    if verb == "describe":
        return {"ok": True, "output": _DESCRIBE_POD, "error": None}

    # Fallback — unknown command
    return {"ok": False, "output": "", "error": f"mock: unrecognised command args={args}"}
