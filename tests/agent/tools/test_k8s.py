import json

import services.agent.tools.k8s as k8s_mod
from services.agent.tools.k8s import (
    get_deployment,
    get_deployment_history,
    get_events,
    get_pod_logs,
    get_pod_logs_previous,
    get_pod_status,
    list_deployment_pods,
)


def _ok(output: str = "") -> dict:
    return {"ok": True, "output": output, "error": None, "truncated": False}


def test_get_pod_status_builds_path_and_summarizes(monkeypatch):
    captured: dict[str, str] = {}

    def _fake_get(path):
        captured["path"] = path
        return _ok(
            json.dumps(
                {
                    "metadata": {"name": "auth-abc"},
                    "spec": {"nodeName": "node-1"},
                    "status": {
                        "phase": "Running",
                        "containerStatuses": [
                            {
                                "name": "app",
                                "ready": True,
                                "restartCount": 3,
                                "lastState": {
                                    "terminated": {
                                        "reason": "OOMKilled",
                                        "exitCode": 137,
                                    }
                                },
                            }
                        ],
                    },
                }
            )
        )

    monkeypatch.setattr(k8s_mod, "k8s_get", _fake_get)

    result = get_pod_status("production", "auth-abc")

    assert captured["path"] == "/api/v1/namespaces/production/pods/auth-abc"
    output = json.loads(result["output"])
    assert output["name"] == "auth-abc"
    assert output["phase"] == "Running"
    assert output["containers"][0]["last_state"]["terminated"]["reason"] == "OOMKilled"


def test_pod_logs_build_tail_and_previous_query(monkeypatch):
    captured: list[str] = []

    def _fake_get(path):
        captured.append(path)
        return _ok("exit code 137: OOMKilled")

    monkeypatch.setattr(k8s_mod, "k8s_get", _fake_get)

    result = get_pod_logs_previous(
        "production", "auth-pod", tail=50, container="app"
    )

    assert result["output"] == "exit code 137: OOMKilled"
    assert captured == [
        "/api/v1/namespaces/production/pods/auth-pod/log"
        "?tailLines=50&previous=true&container=app"
    ]


def test_pod_logs_uses_default_tail(monkeypatch):
    captured: list[str] = []
    monkeypatch.setattr(
        k8s_mod, "k8s_get", lambda path: captured.append(path) or _ok("logs")
    )

    get_pod_logs("production", "auth-pod")

    assert captured == [
        "/api/v1/namespaces/production/pods/auth-pod/log?tailLines=200"
    ]


def test_invalid_names_are_rejected_before_http(monkeypatch):
    def _forbidden(_path):
        raise AssertionError("HTTP must not run for an invalid name")

    monkeypatch.setattr(k8s_mod, "k8s_get", _forbidden)

    result = get_pod_logs("../etc", "auth-pod")

    assert result["ok"] is False
    assert "namespace" in result["error"]


def test_get_deployment_projects_rollout_state(monkeypatch):
    captured: dict[str, str] = {}

    def _fake_get(path):
        captured["path"] = path
        return _ok(
            json.dumps(
                {
                    "metadata": {"name": "auth-service", "generation": 5},
                    "spec": {
                        "replicas": 3,
                        "template": {
                            "spec": {
                                "containers": [{"image": "auth-service:v2"}]
                            }
                        },
                    },
                    "status": {
                        "observedGeneration": 5,
                        "readyReplicas": 1,
                        "availableReplicas": 1,
                        "unavailableReplicas": 2,
                    },
                }
            )
        )

    monkeypatch.setattr(k8s_mod, "k8s_get", _fake_get)

    result = get_deployment("production", "auth-service")

    assert captured["path"] == (
        "/apis/apps/v1/namespaces/production/deployments/auth-service"
    )
    output = json.loads(result["output"])
    assert output["desired_replicas"] == 3
    assert output["ready_replicas"] == 1
    assert output["unavailable_replicas"] == 2
    assert output["images"] == ["auth-service:v2"]


def test_list_deployment_pods_follows_the_deployment_selector(monkeypatch):
    paths: list[str] = []

    def _fake_get(path):
        paths.append(path)
        if "/deployments/" in path:
            return _ok(
                json.dumps(
                    {
                        "spec": {
                            "selector": {"matchLabels": {"app": "auth-service"}}
                        }
                    }
                )
            )
        return _ok(
            json.dumps(
                {
                    "items": [
                        {
                            "metadata": {"name": "auth-abc"},
                            "spec": {"nodeName": "node-1"},
                            "status": {
                                "phase": "Running",
                                "containerStatuses": [
                                    {"name": "app", "ready": False, "restartCount": 7}
                                ],
                            },
                        }
                    ]
                }
            )
        )

    monkeypatch.setattr(k8s_mod, "k8s_get", _fake_get)

    result = list_deployment_pods("production", "auth-service")

    assert paths == [
        "/apis/apps/v1/namespaces/production/deployments/auth-service",
        "/api/v1/namespaces/production/pods?labelSelector=app%3Dauth-service",
    ]
    output = json.loads(result["output"])
    assert output["selector"] == "app=auth-service"
    assert output["pods"][0]["name"] == "auth-abc"
    assert output["pods"][0]["restarts"] == 7


def test_deployment_history_sorts_revisions_newest_first(monkeypatch):
    def _fake_get(path):
        if "/deployments/" in path:
            return _ok(
                json.dumps(
                    {
                        "metadata": {
                            "annotations": {
                                "deployment.kubernetes.io/revision": "3"
                            }
                        },
                        "spec": {
                            "selector": {"matchLabels": {"app": "auth-service"}}
                        },
                    }
                )
            )
        return _ok(
            json.dumps(
                {
                    "items": [
                        {
                            "metadata": {
                                "name": "auth-rs-1",
                                "annotations": {
                                    "deployment.kubernetes.io/revision": "1"
                                },
                            }
                        },
                        {
                            "metadata": {
                                "name": "auth-rs-3",
                                "annotations": {
                                    "deployment.kubernetes.io/revision": "3"
                                },
                            }
                        },
                        {
                            "metadata": {
                                "name": "auth-rs-2",
                                "annotations": {
                                    "deployment.kubernetes.io/revision": "2"
                                },
                            }
                        },
                    ]
                }
            )
        )

    monkeypatch.setattr(k8s_mod, "k8s_get", _fake_get)

    result = get_deployment_history("production", "auth-service")

    output = json.loads(result["output"])
    assert output["current_revision"] == "3"
    assert [item["revision"] for item in output["revisions"]] == ["3", "2", "1"]


def test_events_requests_warnings_and_projects_them(monkeypatch):
    captured: dict[str, str] = {}

    def _fake_get(path):
        captured["path"] = path
        return _ok(
            json.dumps(
                {
                    "items": [
                        {
                            "type": "Warning",
                            "reason": "OOMKilling",
                            "message": "Memory limit exceeded",
                            "count": 4,
                            "lastTimestamp": "2026-11-05T10:00:00Z",
                            "involvedObject": {
                                "kind": "Pod",
                                "name": "auth-abc",
                            },
                        }
                    ]
                }
            )
        )

    monkeypatch.setattr(k8s_mod, "k8s_get", _fake_get)

    result = get_events("production")

    assert captured["path"] == (
        "/api/v1/namespaces/production/events"
        "?fieldSelector=type%3DWarning&limit=100"
    )
    output = json.loads(result["output"])
    assert output["events"][0]["reason"] == "OOMKilling"
    assert output["events"][0]["object"] == "Pod/auth-abc"


def test_non_json_response_becomes_a_clear_failure(monkeypatch):
    monkeypatch.setattr(k8s_mod, "k8s_get", lambda _path: _ok("not json"))

    result = get_pod_status("production", "auth-abc")

    assert result["ok"] is False
    assert "non-JSON" in result["error"]
