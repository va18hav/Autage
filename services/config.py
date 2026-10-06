from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    GOOGLE_API_KEY: str
    MOCK_KUBECTL: bool
    REDIS_URL: str = "redis://localhost:6379/0"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "autage"
    DB_PASSWORD: str = "autage_password"
    DB_NAME: str = "autage"
    WEBHOOK_SECRET: str

    # Master key (Fernet) used to encrypt integration credentials at rest.
    # Generate once with: uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    AUTAGE_SECRET_KEY: str | None = None

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

settings = Settings()