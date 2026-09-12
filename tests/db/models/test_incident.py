from services.db.models.incident import (
    Incident,
    IncidentStatus,
    IncidentStep,
    StepStatus,
)


def test_incident_and_step_model_columns_and_enums():
    assert Incident.__tablename__ == "incidents"
    assert IncidentStep.__tablename__ == "incident_steps"

    assert [s.value for s in IncidentStatus] == [
        "PENDING",
        "TRIAGING",
        "COMPLETED",
        "FAILED",
    ]
    assert [s.value for s in StepStatus] == ["RUNNING", "COMPLETED", "FAILED"]

    inc = Incident(
        title="Pod CrashLoopBackOff",
        status=IncidentStatus.PENDING,
        raw_alert={"source": "prometheus"},
        fingerprint="abc123",
    )
    step = IncidentStep(
        step_name="triage",
        status=StepStatus.COMPLETED,
        input_data={"raw_alert": {"source": "prometheus"}},
        output_data={"severity": "P1"},
    )
    inc.steps.append(step)
    assert inc.steps[0].step_name == "triage"
    assert step.incident is inc
