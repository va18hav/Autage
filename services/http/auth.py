

from services.config import settings

COOKIE_NAME = "autage_token"
JWT_ALGORITHM = "HS256"


def _jwt_secret() -> str:
    secret = (
        settings.JWT_SECRET_KEY
        or settings.AUTAGE_SECRET_KEY
        or settings.WEBHOOK_SECRET
    )
    return secret
