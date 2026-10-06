from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Provider catalog ──────────────────────────────────────────────────────────

class CredentialFieldOut(BaseModel):
    name: str
    label: str
    is_secret: bool
    required: bool
    default: Optional[str] = None


class ModelOut(BaseModel):
    id: str
    label: str
    tier: str


class ProviderOut(BaseModel):
    id: str
    display_name: str
    models: List[ModelOut]
    credential_fields: List[CredentialFieldOut]
    # Whether a usable credential currently exists for this provider
    credential_configured: bool = False
    # True when the stored key came from the plaintext DB row
    credential_preview: Optional[str] = None


class CatalogResponse(BaseModel):
    providers: List[ProviderOut]
    steps: List["StepKeyOut"]


class StepKeyOut(BaseModel):
    key: str
    label: str


# ── Step configs ──────────────────────────────────────────────────────────────

class StepConfigIn(BaseModel):
    step_key: str = Field(min_length=1)
    provider_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    temperature: Optional[float] = Field(default=None, ge=0, le=2)
    max_output_tokens: Optional[int] = Field(default=None, ge=1)


class StepConfigOut(BaseModel):
    step_key: str
    provider_id: str
    model_id: str
    temperature: Optional[float] = None
    max_output_tokens: Optional[int] = None
    # True when no DB row exists and the built-in default is in effect
    is_default: bool
    # Populated only when this exact provider/model pair has a usable credential
    credential_configured: bool = False


class StepConfigsResponse(BaseModel):
    steps: List[StepConfigOut]


# ── Credential management ─────────────────────────────────────────────────────

class CredentialPayloadIn(BaseModel):
    """Raw credential fields (api_key, base_url, ...) — key names must match
    the provider's `credential_fields` from the catalog."""

    fields: Dict[str, str] = Field(default_factory=dict)


class CredentialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    purpose: str
    preview: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class TestCredentialResponse(BaseModel):
    ok: bool
    provider: Optional[str] = None
    model: Optional[str] = None
    message: str
