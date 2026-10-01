

from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter(prefix="/incidents", tags=["Incidents"])


class SimulateIncidentRequest(BaseModel):
    scenario: str = "oomkill"
