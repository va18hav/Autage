
from fastapi import APIRouter

from services.config import settings
from services.http.routes.settings import WEBHOOK_SECRET_PURPOSE
from services.secrets.store import SecretStore

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


async def _resolve_webhook_secret() -> str | None:
    payload = await SecretStore.fetch_payload(WEBHOOK_SECRET_PURPOSE)
    if payload and payload.get("secret"):
        return str(payload["secret"])
    return settings.WEBHOOK_SECRET or None
