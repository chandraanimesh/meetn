from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    environment: str = "development"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


class DatabaseSettings(BaseSettings):
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "meetn"

    @property
    def async_database_url(self) -> str:
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


class GoogleOIDCSettings(BaseSettings):
    google_client_id: str = "dummy_client_id"
    google_client_secret: str = "dummy_client_secret"
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"
    google_discovery_url: str = "https://accounts.google.com/.well-known/openid-configuration"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


class SessionSettings(BaseSettings):
    session_secret_key: str = "super-secret-key-for-development-only"
    session_max_age_seconds: int = 86400  # 1 day

    @property
    def cookie_secure(self) -> bool:
        return settings.app.environment != "development"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


class GroqSettings(BaseSettings):
    """Groq provider settings with secret-safe credential representation."""

    groq_api_key: SecretStr | None = None
    groq_model: str = "openai/gpt-oss-20b"
    groq_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    groq_max_completion_tokens: int = Field(default=1_024, ge=64, le=4_096)
    groq_reasoning_effort: Literal["low", "medium", "high"] = "low"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class Settings:
    def __init__(self) -> None:
        self.app = AppSettings()
        self.db = DatabaseSettings()
        self.oidc = GoogleOIDCSettings()
        self.session = SessionSettings()
        self.groq = GroqSettings()


settings = Settings()
