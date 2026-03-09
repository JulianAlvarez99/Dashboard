"""
Application configuration — Pydantic Settings.

Loads from .env in the project root.
Phase 2: Flask + FastAPI + Database variables.
"""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # ignore variables we don't use yet (JWT, Argon2, etc.)
    )

    # ── Application ──────────────────────────────────────────────
    APP_NAME: str = "Camet Robotica"
    APP_ENV: str = "development"
    DEBUG: bool = False

    # ── Flask ────────────────────────────────────────────────────
    FLASK_SECRET_KEY: str = ""
    FLASK_PORT: int = 5000

    # ── FastAPI ──────────────────────────────────────────────────
    FASTAPI_PORT: int = 8000
    API_BASE_URL: str = "http://127.0.0.1:8000"

    # Comma-separated CORS origins for FastAPI
    CORS_ALLOWED_ORIGINS: str = "http://localhost:5000,http://127.0.0.1:5000"

    @property
    def cors_origins(self) -> List[str]:
        """Return CORS_ALLOWED_ORIGINS as a list."""
        return [o.strip() for o in self.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]

    # ── Global Database ──────────────────────────────────────────
    GLOBAL_DB_HOST: str = "localhost"
    GLOBAL_DB_PORT: int = 3306
    GLOBAL_DB_USER: str = "root"
    GLOBAL_DB_PASSWORD: str = ""
    GLOBAL_DB_NAME: str = "camet_global"

    # ── Tenant Database ──────────────────────────────────────────
    TENANT_DB_HOST: str = "localhost"
    TENANT_DB_PORT: int = 3306
    TENANT_DB_USER: str = "root"
    TENANT_DB_PASSWORD: str = ""
    TENANT_DB_NAME: str = ""

    # ── Default Tenant (auto-loaded at startup) ──────────────────
    DEFAULT_TENANT_ID: int = 2
    DEFAULT_DB_NAME: str = ""

    # ── Logging ──────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"

    # ── URL Builders ─────────────────────────────────────────────

    def _build_url(self, driver: str, user: str, password: str,
                   host: str, port: int, db_name: str) -> str:
        """Build a SQLAlchemy database URL."""
        cred = f"{user}:{password}" if password else user
        return f"mysql+{driver}://{cred}@{host}:{port}/{db_name}"

    # Global DB URLs
    @property
    def global_db_url_sync(self) -> str:
        return self._build_url(
            "pymysql", self.GLOBAL_DB_USER, self.GLOBAL_DB_PASSWORD,
            self.GLOBAL_DB_HOST, self.GLOBAL_DB_PORT, self.GLOBAL_DB_NAME,
        )

    # Default tenant DB URL (from .env TENANT_DB_NAME)
    @property
    def tenant_db_url_sync(self) -> str:
        return self._build_url(
            "pymysql", self.TENANT_DB_USER, self.TENANT_DB_PASSWORD,
            self.TENANT_DB_HOST, self.TENANT_DB_PORT, self.TENANT_DB_NAME,
        )

    # Dynamic tenant DB URL (resolved at runtime by db_name)
    def tenant_db_url_for(self, db_name: str) -> str:
        """Build sync URL for any tenant database by name."""
        return self._build_url(
            "pymysql", self.TENANT_DB_USER, self.TENANT_DB_PASSWORD,
            self.TENANT_DB_HOST, self.TENANT_DB_PORT, db_name,
        )


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()


# Module-level instance for convenience
settings = get_settings()
