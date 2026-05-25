"""
Application settings.

All config comes from environment variables (loaded from .env in dev).
Import `settings` from here; never read os.environ directly elsewhere.
"""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    # --- General ---
    ENVIRONMENT: str = "development"

    # --- Database / Redis ---
    DATABASE_URL: str
    REDIS_URL: str

    # Render (and Railway) inject plain `postgresql://` or `postgres://` URLs.
    # SQLAlchemy's asyncpg dialect requires `postgresql+asyncpg://`.
    # This validator rewrites the scheme automatically so the app works on both
    # local Docker (where .env already has +asyncpg) and cloud providers.
    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _fix_db_scheme(cls, v: str) -> str:
        if v.startswith("postgres://"):
            v = "postgresql+asyncpg://" + v[len("postgres://"):]
        elif v.startswith("postgresql://"):
            v = "postgresql+asyncpg://" + v[len("postgresql://"):]
        return v

    # --- Auth ---
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    # --- CORS ---
    # Stored as a comma-separated string in .env (e.g. "http://a.com,http://b.com").
    # pydantic-settings auto-JSON-decodes list[str] env vars, so we keep it as
    # str and expose a parsed list via the property below.
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_dev(self) -> bool:
        return self.ENVIRONMENT == "development"


# Singleton — import this everywhere.
settings = Settings()
