from services.agent.tools.kubectl import describe_pod, get_deployment, get_events, get_pod_logs, get_pod_logs_previous, get_pod_status, list_pods, reset_cluster_credentials, set_cluster_credentials

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
