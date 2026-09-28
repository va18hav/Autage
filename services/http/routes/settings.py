
from fastapi import APIRouter


router = APIRouter(prefix="/settings", tags=["Settings"])

WEBHOOK_SECRET_PURPOSE = "webhook_secret"
