
import bcrypt

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


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except ValueError:
        return False
