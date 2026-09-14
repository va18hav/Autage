from datetime import datetime, timezone
from uuid import uuid4

from services.db.models.incident import IncidentStatus, StepStatus
from services.http.schemas.incident import (
    IncidentDetailResponse,
    IncidentListItemResponse,
    IncidentStepResponse,
)


def test_incident_schemas_support_historical_and_list_recommended_steps():
    now = datetime.now(timezone.utc)
    inc_id = uuid4()

    step = IncidentStepResponse(
        id=uuid4(),
        incident_id=inc_id,
        step_name="triage",
        status=StepStatus.COMPLETED,
        input_data={"raw_alert": {}},
        output_data={"severity": "P1"},
        created_at=now,
        updated_at=now,
    )

    item = IncidentListItemResponse(
        id=inc_id,
        title="OOMKill on auth-service",
        status=IncidentStatus.COMPLETED,
        fingerprint="fp123",
        created_at=now,
        updated_at=now,
    )
    assert item.status == IncidentStatus.COMPLETED

    # List[str] shape (current recommended_steps node)
    detail_list = IncidentDetailResponse(
        id=inc_id,
        title="OOMKill on auth-service",
        status=IncidentStatus.COMPLETED,
        raw_alert={"source": "datadog"},
        recommended_steps=["Step 1", "Step 2"],
        steps=[step],
        created_at=now,
        updated_at=now,
    )
    assert detail_list.recommended_steps == ["Step 1", "Step 2"]

    # Dict shape (legacy/seed)
    detail_dict = IncidentDetailResponse(
        id=inc_id,
        title="OOMKill",
        status=IncidentStatus.COMPLETED,
        raw_alert={"source": "datadog"},
        recommended_steps={"steps": ["Step 1"]},
        steps=[],
        created_at=now,
        updated_at=now,
    )
    assert detail_dict.recommended_steps == {"steps": ["Step 1"]}
