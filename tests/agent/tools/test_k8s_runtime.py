import io
import urllib.error

import pytest

import services.agent.tools.k8s_runtime as runtime_mod
from services.agent.tools.k8s_runtime import (
    _http_k8s_get,
    _redact,
    _success,
    k8s_get,
    load_cluster_credentials,
    reset_cluster_credentials,
    set_cluster_credentials,
)


def _complete_credentials() -> dict[str, str]:
    return {
        "server_url": "https://k8s.internal:6443",
        "token": "secret-sa-token-123",
        "ca_cert": "-----BEGIN CERTIFICATE-----\nabc\n-----END CERTIFICATE-----\n",
    }


def test_requires_configured_and_complete_credentials(monkeypatch):
    def _forbidden(*_args, **_kwargs):
        raise AssertionError("HTTP must not run without complete credentials")

    monkeypatch.setattr(runtime_mod, "_http_k8s_get", _forbidden)

    token = set_cluster_credentials(None)
    try:
        result = k8s_get("/api/v1/namespaces")
        assert result["ok"] is False
        assert "not configured" in result["error"]
    finally:
        reset_cluster_credentials(token)

    token = set_cluster_credentials(
        {"server_url": "https://k8s.internal:6443", "token": "sa-token"}
    )
    try:
        result = k8s_get("/api/v1/namespaces")
        assert result["ok"] is False
        assert "incomplete" in result["error"]
        assert "ca_cert" in result["error"]
    finally:
        reset_cluster_credentials(token)


def test_k8s_get_uses_active_cluster(monkeypatch):
    captured: dict[str, str] = {}

    def _fake_http(server_url, token, path, ca_cert):
        captured.update(
            {
                "server_url": server_url,
                "token": token,
                "path": path,
                "ca_cert": ca_cert,
            }
        )
        return {"ok": True, "output": "REST:" + path, "error": None, "truncated": False}

    monkeypatch.setattr(runtime_mod, "_http_k8s_get", _fake_http)

    token = set_cluster_credentials(_complete_credentials())
    try:
        result = k8s_get("/api/v1/namespaces/production/pods/auth-pod/log?tailLines=10")
    finally:
        reset_cluster_credentials(token)

    assert result["ok"] is True
    assert result["output"].endswith("?tailLines=10")
    assert captured == {
        "server_url": "https://k8s.internal:6443",
        "token": "secret-sa-token-123",
        "path": "/api/v1/namespaces/production/pods/auth-pod/log?tailLines=10",
        "ca_cert": _complete_credentials()["ca_cert"].strip(),
    }


def test_relative_path_is_rejected_before_http(monkeypatch):
    calls: list[tuple] = []
    monkeypatch.setattr(
        runtime_mod, "_http_k8s_get", lambda *args: calls.append(args) or {}
    )

    result = k8s_get("api/v1/namespaces")

    assert result["ok"] is False
    assert "must start with" in result["error"]
    assert calls == []


def test_http_get_sends_token_and_uses_cluster_ca(monkeypatch):
    captured: dict = {}

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def read(self):
            return b'{"kind": "PodList"}'

    def _fake_context(cadata=None):
        captured["ca"] = cadata
        return None

    def _fake_urlopen(request, context=None, timeout=None):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["timeout"] = timeout
        return _Response()

    monkeypatch.setattr(runtime_mod.ssl, "create_default_context", _fake_context)
    monkeypatch.setattr(runtime_mod.urllib.request, "urlopen", _fake_urlopen)

    result = _http_k8s_get(
        "https://k8s.internal:6443/",
        "secret-sa-token-123",
        "/api/v1/pods",
        "CA-CERT",
    )

    assert result["ok"] is True
    assert result["output"] == '{"kind": "PodList"}'
    assert captured["url"] == "https://k8s.internal:6443/api/v1/pods"
    assert captured["headers"]["Authorization"] == "Bearer secret-sa-token-123"
    assert captured["ca"] == "CA-CERT"
    assert captured["timeout"] == 20


def test_http_error_is_redacted(monkeypatch):
    monkeypatch.setattr(
        runtime_mod.ssl, "create_default_context", lambda cadata=None: None
    )

    def _forbidden(*_args, **_kwargs):
        raise urllib.error.HTTPError(
            "https://k8s.internal:6443/api/v1/pods",
            403,
            "Forbidden",
            {},
            io.BytesIO(b"token secret-sa-token-123 is not allowed"),
        )

    monkeypatch.setattr(runtime_mod.urllib.request, "urlopen", _forbidden)

    result = _http_k8s_get(
        "https://k8s.internal:6443",
        "secret-sa-token-123",
        "/api/v1/pods",
        "CA",
    )

    assert result["ok"] is False
    assert "403" in result["error"]
    assert "secret-sa-token-123" not in result["error"]
    assert "***" in result["error"]


def test_network_error_is_reported(monkeypatch):
    monkeypatch.setattr(
        runtime_mod.ssl, "create_default_context", lambda cadata=None: None
    )

    def _refused(*_args, **_kwargs):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(runtime_mod.urllib.request, "urlopen", _refused)

    result = _http_k8s_get("https://k8s.internal:6443", "tok", "/api/v1/pods", "CA")

    assert result["ok"] is False
    assert "Could not reach" in result["error"]


def test_output_is_redacted_and_clipped():
    assert _redact("token secret-sa-token-123", "secret-sa-token-123") == "token ***"

    result = _success("x" * 20_000)
    assert result["truncated"] is True
    assert result["output"].endswith("[truncated]")


@pytest.mark.anyio
async def test_load_cluster_credentials(monkeypatch):
    async def _fetch(_purpose):
        return _complete_credentials()

    monkeypatch.setattr(runtime_mod.SecretStore, "fetch_payload", _fetch)

    assert await load_cluster_credentials() == _complete_credentials()


@pytest.mark.anyio
async def test_load_cluster_credentials_missing(monkeypatch):
    async def _fetch(_purpose):
        return None

    monkeypatch.setattr(runtime_mod.SecretStore, "fetch_payload", _fetch)

    assert await load_cluster_credentials() is None
