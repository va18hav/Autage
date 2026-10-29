import json
import os
import subprocess
from types import SimpleNamespace

import services.agent.tools.kubectl_runtime as runtime_mod
from services.agent.tools.kubectl import (
    describe_pod,
    get_pod_logs,
    reset_cluster_credentials,
    set_cluster_credentials,
)


def _complete_credentials() -> dict[str, str]:
    return {
        "server_url": "https://k8s.internal:6443",
        "token": "secret-sa-token-123",
        "ca_cert": "-----BEGIN CERTIFICATE-----\nabc\n-----END CERTIFICATE-----\n",
    }


def test_kubectl_binary_uses_private_kubeconfig_and_redacts_token(monkeypatch):
    token = set_cluster_credentials(_complete_credentials())
    try:
        monkeypatch.setattr(
            runtime_mod.shutil, "which", lambda _cmd: "/usr/local/bin/kubectl"
        )

        captured: dict = {}

        def _fake_run(args, **kwargs):
            kubeconfig_path = kwargs["env"]["KUBECONFIG"]
            captured["args"] = list(args)
            captured["kubeconfig_path"] = kubeconfig_path
            with open(kubeconfig_path) as handle:
                captured["config"] = json.load(handle)
            return SimpleNamespace(
                returncode=1,
                stdout="",
                stderr="error authenticating with token secret-sa-token-123",
            )

        monkeypatch.setattr(runtime_mod.subprocess, "run", _fake_run)
        result = get_pod_logs("production", "auth-pod", tail=20)

        assert result["ok"] is False
        assert "secret-sa-token-123" not in result["error"]
        assert "***" in result["error"]

        # The token must never appear in argv; it lives in a private kubeconfig.
        assert captured["args"] == [
            "kubectl",
            "logs",
            "auth-pod",
            "-n",
            "production",
            "--tail=20",
        ]
        assert not any("secret-sa-token-123" in str(arg) for arg in captured["args"])

        config = captured["config"]
        assert config["clusters"][0]["cluster"]["server"] == "https://k8s.internal:6443"
        assert config["users"][0]["user"]["token"] == "secret-sa-token-123"
        assert "certificate-authority-data" in config["clusters"][0]["cluster"]

        # The temporary kubeconfig is removed after execution.
        assert not os.path.exists(captured["kubeconfig_path"])
    finally:
        reset_cluster_credentials(token)


def test_rest_fallback_requires_complete_credentials(monkeypatch):
    monkeypatch.setattr(runtime_mod.shutil, "which", lambda _cmd: None)

    token = set_cluster_credentials(_complete_credentials())
    try:
        captured = []

        def _fake_http(server_url, token_value, path, ca_cert):
            captured.append((server_url, token_value, path, ca_cert))
            return {
                "ok": True,
                "output": f"REST:{path}",
                "error": None,
                "truncated": False,
            }

        monkeypatch.setattr(runtime_mod, "_http_k8s_get", _fake_http)
        result = get_pod_logs("production", "auth-pod", tail=10)

        assert result["ok"] is True
        assert "/api/v1/namespaces/production/pods/auth-pod/log?tailLines=10" in result["output"]
        assert captured == [
            (
                "https://k8s.internal:6443",
                "secret-sa-token-123",
                "/api/v1/namespaces/production/pods/auth-pod/log?tailLines=10",
                _complete_credentials()["ca_cert"].strip(),
            )
        ]
    finally:
        reset_cluster_credentials(token)

    # Missing CA certificate: fail closed rather than using the host kubeconfig.
    no_ca_token = set_cluster_credentials(
        {"server_url": "https://k8s.internal:6443", "token": "sa-token"}
    )
    try:
        monkeypatch.setattr(
            runtime_mod.shutil, "which", lambda _cmd: "/usr/local/bin/kubectl"
        )

        def _forbidden_run(*_args, **_kwargs):
            raise AssertionError("kubectl must not run with incomplete credentials")

        def _forbidden_http(*_args, **_kwargs):
            raise AssertionError("REST must not run with incomplete credentials")

        monkeypatch.setattr(runtime_mod.subprocess, "run", _forbidden_run)
        monkeypatch.setattr(runtime_mod, "_http_k8s_get", _forbidden_http)

        missing_ca = get_pod_logs("production", "auth-pod", tail=10)
        assert missing_ca["ok"] is False
        assert "incomplete" in missing_ca["error"]
    finally:
        reset_cluster_credentials(no_ca_token)

    # No configured cluster: fail closed with an actionable error.
    no_cluster_token = set_cluster_credentials(None)
    try:
        missing_cluster = get_pod_logs("production", "auth-pod", tail=10)
        assert missing_cluster["ok"] is False
        assert "not configured" in missing_cluster["error"]
    finally:
        reset_cluster_credentials(no_cluster_token)


def test_kubectl_timeout_is_reported(monkeypatch):
    token = set_cluster_credentials(_complete_credentials())
    try:
        monkeypatch.setattr(
            runtime_mod.shutil, "which", lambda _cmd: "/usr/local/bin/kubectl"
        )

        def _timeout_run(*_args, **_kwargs):
            raise subprocess.TimeoutExpired(cmd="kubectl", timeout=20)

        monkeypatch.setattr(runtime_mod.subprocess, "run", _timeout_run)
        result = describe_pod("production", "auth-pod")

        assert result["ok"] is False
        assert "timed out" in result["error"]
    finally:
        reset_cluster_credentials(token)


def test_invalid_names_are_rejected_before_execution():
    result = get_pod_logs("../etc", "auth-pod")

    assert result["ok"] is False
    assert "namespace" in result["error"]
