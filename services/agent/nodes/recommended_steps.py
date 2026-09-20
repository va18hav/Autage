from pydantic import BaseModel, Field
from typing import List




class RecommendedSteps(BaseModel):
    """Concrete, ordered remediation steps handed to the on-call engineer."""
    reasoning: str = Field(description="One-line rationale for the plan")
    recommended_steps: List[str] = Field(description="Ordered list of concrete remediation steps")
