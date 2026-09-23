
from pydantic import BaseModel, Field, field_validator

MAX_HEADING_LENGTH = 255


class RunbookSectionIn(BaseModel):
    heading: str = Field(min_length=1, max_length=MAX_HEADING_LENGTH)
    content: str = Field(max_length=100_000)
    order_index: int = Field(ge=0)

    @field_validator("heading")
    @classmethod
    def strip_heading(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Section heading must not be empty")
        return value

    @field_validator("content")
    @classmethod
    def strip_content(cls, value: str) -> str:
        return value.strip()
