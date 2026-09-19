from services.agent.prompts.fetch_logs import build_plan_prompt

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
