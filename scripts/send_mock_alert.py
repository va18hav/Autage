import sys
from pathlib import Path

# Add project root to sys.path so it works directly from CLI
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


from services.config import settings
from services.http.routes.settings import WEBHOOK_SECRET_PURPOSE
from services.secrets.store import SecretStore


async def _get_active_secret() -> str:
    try:
        payload = await SecretStore.fetch_payload(WEBHOOK_SECRET_PURPOSE)
        if payload and payload.get("secret"):
            return str(payload["secret"])
    except Exception:
        pass
    return settings.WEBHOOK_SECRET
