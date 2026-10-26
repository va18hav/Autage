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


def test_kubectl_binary_execution_masks_token_on_stderr(monkeypatch):
    token = set_cluster_credentials(
        {
            "server_url": "https://k8s.internal:6443/",
            "token": "secret-sa-token-123",
            "ca_cert": "-----BEGIN CERTIFICATE-----\nabc\n-----END CERTIFICATE-----\n",
        }
    )
    try:
        monkeypatch.setattr(kubectl_mod.shutil, "which", lambda _cmd: "/usr/local/bin/kubectl")

        captured_args = []
        ca_file_content = []

        def _fake_run(args, **_kwargs):
            captured_args.extend(args)
            # The real kubectl reads the CA file during execution — mirror that
            # here, because the temp file is deleted when _run() returns.
            for a in args:
                if str(a).startswith("--certificate-authority="):
                    ca_file_content.append(open(str(a).split("=", 1)[1]).read())
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
        # TLS verification is mandatory: the CA is always passed and no
        # skip-verify flag may appear.
        ca_flags = [a for a in captured_args if a.startswith("--certificate-authority=")]
        assert len(ca_flags) == 1
        assert "-----BEGIN CERTIFICATE-----" in ca_file_content[0]
        assert not any("insecure" in str(a) for a in captured_args)
    finally:
        reset_cluster_credentials(token)


def test_kubectl_rest_fallback_and_timeout_handling(monkeypatch):
    token = set_cluster_credentials(
        {
            "server_url": "https://k8s.internal:6443",
            "token": "sa-token",
            "ca_cert": "-----BEGIN CERT-----",
        }
    )
    try:
        # When kubectl binary is absent, falls back to _http_k8s_get
        monkeypatch.setattr(kubectl_mod.shutil, "which", lambda _cmd: None)
        monkeypatch.setattr(
            kubectl_mod,
            "_http_k8s_get",
            lambda server_url, tok, path, ca, accept="application/json": {
                "ok": True,
                "output": f"REST:{server_url}{path}:{accept} CA:{ca}",
                "error": None,
            },
        )
        res = get_pod_logs("production", "auth-pod", tail=10)
        assert res["ok"] is True
        assert "/api/v1/namespaces/production/pods/auth-pod/log?tailLines=10" in res["output"]
        assert "CA:-----BEGIN CERT-----" in res["output"]

        # No DB cluster without a CA certificate → bare local kubectl path
        no_ca_token = set_cluster_credentials(
            {"server_url": "https://k8s.internal:6443", "token": "sa-token"}
        )
        try:
            monkeypatch.setattr(kubectl_mod.shutil, "which", lambda _cmd: None)
            executed = []

            def _bare_run(args, **_kw):
                executed.append(args)
                raise FileNotFoundError("kubectl")

            monkeypatch.setattr(kubectl_mod.subprocess, "run", _bare_run)
            no_ca_res = get_pod_logs("production", "auth-pod", tail=10)
            # The DB-configured URL must NOT be used without a CA cert; the
            # call fell through to the local kubectl path.
            assert not any(
                any(str(a).startswith("--server=") for a in c) for c in executed
            )
            assert "kubectl binary not found" in no_ca_res["error"]
        finally:
            reset_cluster_credentials(no_ca_token)

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
