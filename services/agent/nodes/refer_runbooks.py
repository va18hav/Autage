from typing import List
from pydantic import BaseModel, Field



class SectionRequest(BaseModel):
    """A runbook section the LLM wants the content of."""
    runbook_title: str          = Field(description="Title of the runbook containing the section")
    section_order_index: int    = Field(description="order_index of the section within that runbook")


class SectionsSelection(BaseModel):
    """Which runbook sections to pull the full content of."""
    reasoning: str              = Field(description="Brief reasoning for why these sections were chosen")
    sections: List[SectionRequest] = Field(description="Sections to load; empty list if none are relevant")
