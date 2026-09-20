from enum import Enum
from pydantic import BaseModel, Field

class Severity(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"

class AlertTriage(BaseModel):
    incident_title: str = Field(description="Title of the incident")
    description: str = Field(description="Incident description")
    severity: Severity = Field(description="Severity: P1, P2, or P3")
    summary: str = Field(description="Concise 2-3 sentence summary of incident and impact")
