from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    GOOGLE_API_KEY: str = ""
    MOCK_KUBECTL: bool = True
    REDIS_URL: str = "redis://localhost:6379/0"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "autage"
    DB_PASSWORD: str = "autage_password"
    DB_NAME: str = "autage"
    WEBHOOK_SECRET: str = "autage-webhook-secret"

    # Master key (Fernet) used to encrypt integration credentials at rest.
    # Generate once with: uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    AUTAGE_SECRET_KEY: str | None = None

    # JWT signing secret and session duration (defaults to AUTAGE_SECRET_KEY or WEBHOOK_SECRET if unset)
    JWT_SECRET_KEY: str | None = None
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    COOKIE_SECURE: bool = False

    # Comma-separated list of allowed CORS origins for the web dashboard
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Verify Kubernetes API Server TLS certificates (set True in production with valid CA certs)
    K8S_VERIFY_SSL: bool = False

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

settings = Settings()