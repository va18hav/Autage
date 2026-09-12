from services.agent.prompts.fetch_logs import (
    build_plan_prompt,
    build_recommended_steps_prompt,
    build_runbook_selection_prompt,
    build_summary_prompt,
)


def test_build_plan_prompt_toggles_runbook_instructions():
    with_rb = build_plan_prompt(
        raw_alert={"pod": "api-1"},
        incident_title="CrashLoop",
        severity="P1",
        summary="Pod crashing",
        runbooks_available=True,
    )
    assert "setting runbooks_needed=true" in with_rb

    without_rb = build_plan_prompt(
        raw_alert={"pod": "api-1"},
        incident_title="CrashLoop",
        severity="P1",
        summary="Pod crashing",
        runbooks_available=False,
    )
    assert "No runbooks are saved in the database" in without_rb


def test_build_summary_runbook_selection_and_recommended_steps_prompts():
    summary_prompt = build_summary_prompt(
        incident_title="OOMKill",
        severity="P1",
        summary="Pod OOM",
        logs={
            "get_pod_logs:api-1": {"ok": True, "output": "Out of memory", "error": None},
            "describe_pod:api-1": {"ok": False, "output": "", "error": "timeout"},
        },
    )
    assert "get_pod_logs:api-1 [SUCCESS]" in summary_prompt
    assert "describe_pod:api-1 [FAILED]" in summary_prompt

    rb_prompt = build_runbook_selection_prompt(
        incident_title="OOMKill",
        severity="P1",
        summary="Pod OOM",
        logs_summary="Exit code 137",
        runbooks=[
            {
                "runbook_title": "OOM Runbook",
                "service": "auth",
                "sections": [{"order_index": 0, "heading": "Increase Limits"}],
            },
            {
                "runbook_title": "Empty Runbook",
                "service": None,
                "sections": [],
            },
        ],
    )
    assert "[0] Increase Limits" in rb_prompt
    assert "(no sections)" in rb_prompt

    rec_prompt = build_recommended_steps_prompt(
        incident_title="OOMKill",
        severity="P1",
        summary="Pod OOM",
        logs_summary="Exit code 137",
        runbooks_summary="",
    )
    assert "No runbooks were consulted for this incident." in rec_prompt
