"""
Application configuration — Pydantic Settings.

Loads from .env with strict validation. Single source of truth
for all environment-dependent values.
"""

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────
    APP_NAME: str = "CametAnalytics"
    APP_ENV: str = "development"
    DEBUG: bool = False
    SECRET_KEY: str = ""

    # ── Flask ────────────────────────────────────────────────────
    FLASK_SECRET_KEY: str = ""
    FLASK_PORT: int = 5000
    API_BASE_URL: str = "http://127.0.0.1:8000"
    # Comma-separated list of allowed CORS origins for the FastAPI server.
    # In production set to your actual domain, e.g.: https://yourdomain.com
    CORS_ALLOWED_ORIGINS: str = "http://localhost:5000,http://127.0.0.1:5000"
    # Shared secret for internal FastAPI endpoints (cache load/refresh).
    # Must be provided; Flask sends this in X-Internal-Key header.
    API_INTERNAL_KEY: str = ""

    # ── Global Database (camet_global) ───────────────────────────
    GLOBAL_DB_HOST: str = "localhost"
    GLOBAL_DB_PORT: int = 3306
    GLOBAL_DB_NAME: str = "camet_global"
    GLOBAL_DB_USER: str = "root"
    GLOBAL_DB_PASSWORD: str = ""

    # ── Tenant Database (template — overridden per tenant) ───────
    TENANT_DB_HOST: str = "localhost"
    TENANT_DB_PORT: int = 3306
    TENANT_DB_NAME: str = ""
    TENANT_DB_USER: str = "root"
    TENANT_DB_PASSWORD: str = ""

    # ── JWT (reserved for future API auth) ───────────────────────
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"

    # ── CORS origins (parsed property) ───────────────────────────
    @property
    def cors_origins(self) -> List[str]:
        """Return CORS_ALLOWED_ORIGINS as a list."""
        return [o.strip() for o in self.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Argon2 ───────────────────────────────────────────────────
    ARGON2_TIME_COST: int = 2
    ARGON2_MEMORY_COST: int = 65536
    ARGON2_PARALLELISM: int = 1

    # ── Security ─────────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 100
    SESSION_TIMEOUT_MINUTES: int = 30

    # ── Data limits ──────────────────────────────────────────────
    # Maximum rows fetched across all pagination batches.
    # Reduce on shared hosting with tight RAM limits (e.g. 100_000).
    MAX_EXPORT_ROWS: int = 100_000

    # ── UI feature flags ─────────────────────────────────────────
    SHOW_OEE_TAB: bool = False

    # ── Logging ──────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"

    # ── Startup validators ────────────────────────────────────────

    @field_validator("FLASK_SECRET_KEY", "SECRET_KEY")
    @classmethod
    def _require_flask_secrets(cls, v: str, info) -> str:
        """Refuse to start if Flask/app secret keys are empty."""
        if not v or not v.strip():
            raise ValueError(
                f"{info.field_name} must not be empty. "
                "Set it in your .env file (min 32 random characters)."
            )
        return v

    @field_validator("API_INTERNAL_KEY")
    @classmethod
    def _require_internal_key(cls, v: str, info) -> str:
        """Refuse to start if API_INTERNAL_KEY is empty."""
        if not v or not v.strip():
            raise ValueError(
                "API_INTERNAL_KEY must not be empty. "
                "Set a strong random value in your .env file."
            )
        return v

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def _require_jwt_secret(cls, v: str, info) -> str:
        """Refuse to start if JWT_SECRET_KEY is empty."""
        if not v or not v.strip():
            raise ValueError(
                "JWT_SECRET_KEY must not be empty. "
                "Set a strong random value in your .env file (min 32 characters)."
            )
        return v

    # ── URL Builders ─────────────────────────────────────────────

    def _build_url(self, driver: str, user: str, password: str,
                   host: str, port: int, db_name: str) -> str:
        """Build a SQLAlchemy database URL."""
        cred = f"{user}:{password}" if password else user
        return f"mysql+{driver}://{cred}@{host}:{port}/{db_name}"

    # Global DB
    @property
    def global_db_url(self) -> str:
        return self._build_url(
            "aiomysql", self.GLOBAL_DB_USER, self.GLOBAL_DB_PASSWORD,
            self.GLOBAL_DB_HOST, self.GLOBAL_DB_PORT, self.GLOBAL_DB_NAME,
        )

    @property
    def global_db_url_sync(self) -> str:
        return self._build_url(
            "pymysql", self.GLOBAL_DB_USER, self.GLOBAL_DB_PASSWORD,
            self.GLOBAL_DB_HOST, self.GLOBAL_DB_PORT, self.GLOBAL_DB_NAME,
        )

    # Default tenant DB (from .env — used as fallback)
    @property
    def tenant_db_url(self) -> str:
        return self._build_url(
            "aiomysql", self.TENANT_DB_USER, self.TENANT_DB_PASSWORD,
            self.TENANT_DB_HOST, self.TENANT_DB_PORT, self.TENANT_DB_NAME,
        )

    @property
    def tenant_db_url_sync(self) -> str:
        return self._build_url(
            "pymysql", self.TENANT_DB_USER, self.TENANT_DB_PASSWORD,
            self.TENANT_DB_HOST, self.TENANT_DB_PORT, self.TENANT_DB_NAME,
        )

    # Dynamic tenant DB (resolved at login from tenant.config_tenant)
    def tenant_db_url_for(self, db_name: str, driver: str = "aiomysql") -> str:
        """Build URL for any tenant database by name."""
        return self._build_url(
            driver, self.TENANT_DB_USER, self.TENANT_DB_PASSWORD,
            self.TENANT_DB_HOST, self.TENANT_DB_PORT, db_name,
        )


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()


settings = get_settings()
