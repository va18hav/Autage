from pydantic import BaseModel, Field



class SectionRequest(BaseModel):
    """A runbook section the LLM wants the content of."""
    runbook_title: str          = Field(description="Title of the runbook containing the section")
    section_order_index: int    = Field(description="order_index of the section within that runbook")
