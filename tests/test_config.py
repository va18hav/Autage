from services.config import Settings


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
