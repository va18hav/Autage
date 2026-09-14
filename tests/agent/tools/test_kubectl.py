import subprocess
from types import SimpleNamespace

import services.agent.tools.kubectl as kubectl_mod
from services.agent.tools.kubectl import (
    describe_pod,
    get_deployment,
    get_events,
    get_pod_logs,
    get_pod_logs_previous,
    get_pod_status,
    list_pods,
    reset_cluster_credentials,
    set_cluster_credentials,
)


def test_mock_kubectl_responses_when_no_cluster_configured():
    token = set_cluster_credentials(None)
    try:
        assert get_pod_logs("production", "auth-service-xyz", tail=50)["ok"] is True
        assert "Out of memory" in get_pod_logs_previous("production", "auth-service-xyz", tail=50)["output"]
        assert get_pod_status("production", "auth-service-xyz")["ok"] is True
        assert "OOMKilled" in describe_pod("production", "auth-service-xyz")["output"]
        assert "OOMKilling" in get_events("production")["output"]
        assert list_pods("production")["ok"] is True
        assert "RollingUpdate" in get_deployment("production", "auth-service")["output"]
    finally:
        reset_cluster_credentials(token)


def test_kubectl_binary_execution_masks_token_on_stderr(monkeypatch):
    token = set_cluster_credentials(
        {"server_url": "https://k8s.internal:6443/", "token": "secret-sa-token-123"}
    )
    try:
        monkeypatch.setattr(kubectl_mod.shutil, "which", lambda _cmd: "/usr/local/bin/kubectl")

        captured_args = []

        def _fake_run(args, **_kwargs):
            captured_args.extend(args)
            return SimpleNamespace(
                returncode=1,
                stdout="",
                stderr="error authenticating with token secret-sa-token-123",
            )

        monkeypatch.setattr(kubectl_mod.subprocess, "run", _fake_run)
        res = get_pod_logs("production", "auth-pod", tail=20)

        assert res["ok"] is False
        assert "secret-sa-token-123" not in res["error"]
        assert "***" in res["error"]
        assert "--server=https://k8s.internal:6443" in captured_args
    finally:
        reset_cluster_credentials(token)


def test_kubectl_rest_fallback_and_timeout_handling(monkeypatch):
    token = set_cluster_credentials(
        {"server_url": "https://k8s.internal:6443", "token": "sa-token"}
    )
    try:
        # When kubectl binary is absent, falls back to _http_k8s_get
        monkeypatch.setattr(kubectl_mod.shutil, "which", lambda _cmd: None)
        monkeypatch.setattr(
            kubectl_mod,
            "_http_k8s_get",
            lambda server_url, tok, path, accept="application/json": {
                "ok": True,
                "output": f"REST:{server_url}{path}:{accept}",
                "error": None,
            },
        )
        res = get_pod_logs("production", "auth-pod", tail=10)
        assert res["ok"] is True
        assert "/api/v1/namespaces/production/pods/auth-pod/log?tailLines=10" in res["output"]

        # Timeout handling when kubectl binary hangs
        monkeypatch.setattr(kubectl_mod.shutil, "which", lambda _cmd: "/usr/local/bin/kubectl")

        def _timeout_run(*_a, **_kw):
            raise subprocess.TimeoutExpired(cmd="kubectl", timeout=20)

        monkeypatch.setattr(kubectl_mod.subprocess, "run", _timeout_run)
        timeout_res = describe_pod("production", "auth-pod")
        assert timeout_res["ok"] is False
        assert "timed out" in timeout_res["error"]
    finally:
        reset_cluster_credentials(token)
