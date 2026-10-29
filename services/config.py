from urllib.parse import quote_plus

from cryptography.fernet import Fernet
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    GOOGLE_API_KEY: str = ""
    REDIS_URL: str = "redis://localhost:6379/0"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "autage"
    DB_PASSWORD: str
    DB_NAME: str = "autage"

    @field_validator("DB_PASSWORD")
    @classmethod
    def validate_db_password(cls, value: str) -> str:
        password = value.strip()
        if not password:
            raise ValueError(
                "DB_PASSWORD is required. Set a strong database password in .env."
            )
        return password

    # Required master key (Fernet) used to encrypt integration credentials at rest.
    # Generate once with: uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    AUTAGE_SECRET_KEY: str

    @field_validator("AUTAGE_SECRET_KEY")
    @classmethod
    def validate_autage_secret_key(cls, value: str) -> str:
        key = value.strip()
        if not key:
            raise ValueError(
                "AUTAGE_SECRET_KEY is required. Generate one with: "
                'uv run python -c "from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())"'
            )
        try:
            Fernet(key.encode())
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "AUTAGE_SECRET_KEY must be a valid Fernet key. Generate one with: "
                'uv run python -c "from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())"'
            ) from exc
        return key

    # Optional bootstrap/recovery token used to create the first user or reset
    # the administrator password. Keep it secret and in the deployment env.
    # Generate with: uv run python -c "import secrets; print(secrets.token_urlsafe(48))"
    AUTAGE_SETUP_TOKEN: str | None = None

    # Required, independent secret used only for signing login sessions.
    # Generate with: uv run python -c "import secrets; print(secrets.token_urlsafe(48))"
    JWT_SECRET_KEY: str
    JWT_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    COOKIE_SECURE: bool = False

    # Postgres-backed incident worker.
    WORKER_POLL_SECONDS: float = 1.0
    WORKER_MAX_ATTEMPTS: int = 3
    WORKER_RETRY_DELAY_SECONDS: int = 30
    WORKER_JOB_TIMEOUT_SECONDS: int = 15 * 60

    @field_validator("AUTAGE_SETUP_TOKEN")
    @classmethod
    def validate_autage_setup_token(cls, value: str | None) -> str | None:
        if value is None:
            return None
        token = value.strip()
        if not token:
            return None
        if len(token) < 32:
            raise ValueError(
                "AUTAGE_SETUP_TOKEN must be at least 32 characters. Generate one with: "
                'uv run python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        return token

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret_key(cls, value: str) -> str:
        key = value.strip()
        if len(key) < 32:
            raise ValueError(
                "JWT_SECRET_KEY must be at least 32 characters. Generate one with: "
                'uv run python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        return key

    @model_validator(mode="after")
    def validate_independent_secrets(self) -> "Settings":
        if self.JWT_SECRET_KEY == self.AUTAGE_SECRET_KEY:
            raise ValueError(
                "JWT_SECRET_KEY must be different from AUTAGE_SECRET_KEY. "
                "Generate a dedicated JWT signing key."
            )
        if self.AUTAGE_SETUP_TOKEN in {
            self.AUTAGE_SECRET_KEY,
            self.JWT_SECRET_KEY,
            self.DB_PASSWORD,
        }:
            raise ValueError(
                "AUTAGE_SETUP_TOKEN must be different from all other secrets. "
                "Generate a dedicated setup token."
            )
        return self

    # Comma-separated list of allowed CORS origins for the web dashboard
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{quote_plus(self.DB_USER)}:"
            f"{quote_plus(self.DB_PASSWORD)}@{self.DB_HOST}:{self.DB_PORT}/"
            f"{quote_plus(self.DB_NAME)}"
        )

    @property
    def psycopg_database_url(self) -> str:
        """Connection URL for psycopg-based LangGraph checkpoints."""
        return (
            f"postgresql://{quote_plus(self.DB_USER)}:"
            f"{quote_plus(self.DB_PASSWORD)}@{self.DB_HOST}:{self.DB_PORT}/"
            f"{quote_plus(self.DB_NAME)}"
        )

settings = Settings()
