"""
Application settings.

All config comes from environment variables (loaded from .env in dev).
Import `settings` from here; never read os.environ directly elsewhere.
"""

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
