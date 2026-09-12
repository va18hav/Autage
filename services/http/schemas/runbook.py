from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

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


class RunbookCreate(BaseModel):
    title: str = Field(min_length=1, max_length=MAX_HEADING_LENGTH)
    description: Optional[str] = None
    service: Optional[str] = None
    triggers: Optional[List[str]] = None
    raw_content: str = Field(max_length=1_000_000)
    sections: List[RunbookSectionIn] = Field(max_length=200)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Runbook title must not be empty")
        return value

    @field_validator("service")
    @classmethod
    def blank_service_to_none(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            return None
        return value

    @field_validator("triggers")
    @classmethod
    def drop_empty_triggers(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return None
        cleaned = [t.strip() for t in value if t and t.strip()]
        return cleaned or None


class RunbookSectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    runbook_id: UUID
    order_index: int
    heading: str
    content: str
    created_at: datetime
    updated_at: datetime


class RunbookListItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: Optional[str] = None
    service: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class RunbookDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: Optional[str] = None
    service: Optional[str] = None
    triggers: Optional[List[str]] = None
    raw_content: str
    sections: List[RunbookSectionResponse] = []
    created_at: datetime
    updated_at: datetime
