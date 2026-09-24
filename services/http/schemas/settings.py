from typing import List, Optional

from pydantic import BaseModel


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
