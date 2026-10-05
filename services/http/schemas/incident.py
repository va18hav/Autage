from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict

from services.db.models.incident import IncidentStatus, StepStatus

class IncidentStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    incident_id: UUID
    step_name: str
    status: StepStatus
    input_data: Optional[dict[str, Any]] = None
    output_data: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class IncidentListItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    status: IncidentStatus
    fingerprint: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class IncidentDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    status: IncidentStatus
    fingerprint: Optional[str] = None
    raw_alert: dict[str, Any]
    recommended_steps: Optional[dict[str, Any] | str] = None
    steps: List[IncidentStepResponse] = []
    created_at: datetime
    updated_at: datetime