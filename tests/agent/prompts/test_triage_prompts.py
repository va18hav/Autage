from services.agent.prompts.triage import build_system_prompt


def test_build_triage_system_prompt_embeds_raw_alert_and_incident_types():
    raw_alert = {
        "source": "datadog",
        "pod_name": "auth-service-7d84b8f58b-xyz",
        "metric": "container.memory.usage",
    }
    prompt = build_system_prompt(raw_alert)

    assert "auth-service-7d84b8f58b-xyz" in prompt
    assert "P1:" in prompt and "P2:" in prompt and "P3:" in prompt
    assert "crash_loop" in prompt
    assert "bad_deployment" in prompt
    assert "other" in prompt
    assert "incident title" in prompt
    assert "untrusted monitoring data" in prompt
    assert "Do not choose diagnostic commands" in prompt
    assert "Never guess" in prompt
