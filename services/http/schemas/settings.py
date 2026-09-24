from typing import Optional

from pydantic import BaseModel


# ── Provider catalog ──────────────────────────────────────────────────────────

class CredentialFieldOut(BaseModel):
    name: str
    label: str
    is_secret: bool
    required: bool
    default: Optional[str] = None
