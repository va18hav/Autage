import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from services.config import Settings


def test_settings_requires_autage_secret_key(monkeypatch):
    monkeypatch.delenv("AUTAGE_SECRET_KEY", raising=False)

    with pytest.raises(ValidationError, match="AUTAGE_SECRET_KEY"):
        Settings(_env_file=None)


def test_settings_rejects_invalid_autage_secret_key():
    with pytest.raises(ValidationError, match="valid Fernet key"):
        Settings(_env_file=None, AUTAGE_SECRET_KEY="not-a-fernet-key")


def test_settings_accepts_valid_autage_secret_key():
    key = Fernet.generate_key().decode()

    cfg = Settings(_env_file=None, AUTAGE_SECRET_KEY=f"  {key}  ")

    assert cfg.AUTAGE_SECRET_KEY == key


def test_settings_defaults_jwt_lifetime_to_24_hours():
    cfg = Settings(_env_file=None)

    assert cfg.JWT_EXPIRE_MINUTES == 60 * 24


def test_settings_requires_jwt_secret_key(monkeypatch):
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        Settings(_env_file=None)


def test_settings_rejects_short_jwt_secret_key():
    with pytest.raises(ValidationError, match="at least 32 characters"):
        Settings(_env_file=None, JWT_SECRET_KEY="too-short")


def test_settings_rejects_jwt_secret_reused_from_another_secret():
    encryption_key = Fernet.generate_key().decode()

    with pytest.raises(ValidationError, match="must be different"):
        Settings(
            _env_file=None,
            AUTAGE_SECRET_KEY=encryption_key,
            JWT_SECRET_KEY=encryption_key,
        )


def test_settings_rejects_short_setup_token():
    with pytest.raises(ValidationError, match="at least 32 characters"):
        Settings(_env_file=None, AUTAGE_SETUP_TOKEN="too-short")


def test_settings_rejects_setup_token_reused_from_another_secret():
    encryption_key = Fernet.generate_key().decode()

    with pytest.raises(ValidationError, match="must be different"):
        Settings(
            _env_file=None,
            AUTAGE_SECRET_KEY=encryption_key,
            AUTAGE_SETUP_TOKEN=encryption_key,
        )


def test_settings_treats_blank_setup_token_as_not_configured():
    cfg = Settings(_env_file=None, AUTAGE_SETUP_TOKEN="   ")

    assert cfg.AUTAGE_SETUP_TOKEN is None


def test_settings_requires_db_password(monkeypatch):
    monkeypatch.delenv("DB_PASSWORD", raising=False)

    with pytest.raises(ValidationError, match="DB_PASSWORD"):
        Settings(_env_file=None)


def test_settings_rejects_blank_db_password():
    with pytest.raises(ValidationError, match="DB_PASSWORD is required"):
        Settings(_env_file=None, DB_PASSWORD="   ")


def test_settings_database_url_construction():
    cfg = Settings(
        DB_USER="sre",
        DB_PASSWORD="secret",
        DB_HOST="db.internal",
        DB_PORT=5433,
        DB_NAME="autage_prod",
    )
    assert cfg.database_url == "postgresql+asyncpg://sre:secret@db.internal:5433/autage_prod"


def test_settings_cors_origins_list_parsing():
    cfg = Settings(CORS_ORIGINS=" https://autage.dev , http://localhost:5173 , ")
    assert cfg.cors_origins_list == ["https://autage.dev", "http://localhost:5173"]


def test_settings_rejects_wildcard_cors_origin():
    with pytest.raises(ValidationError, match="cannot contain"):
        Settings(CORS_ORIGINS="*")


def test_settings_rejects_invalid_cors_origin():
    with pytest.raises(ValidationError, match="invalid origin"):
        Settings(CORS_ORIGINS="autage.dev")


def test_settings_rejects_empty_cors_origins():
    with pytest.raises(ValidationError, match="at least one"):
        Settings(CORS_ORIGINS=" , ")
