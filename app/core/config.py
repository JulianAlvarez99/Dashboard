"""
Application configuration using Pydantic Settings
Loads from .env file with validation
"""

from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Application
    APP_NAME: str = "Dashboard_SaaS"
    APP_ENV: str = "development"
    DEBUG: bool = False
    SECRET_KEY: str = ""  # Required in .env
    
    # Flask
    FLASK_SECRET_KEY: str = ""  # Required in .env
    FLASK_PORT: int = 5000
    API_BASE_URL: str = "http://localhost:8000"
    
    # Global Database (Camet_Global)
    GLOBAL_DB_HOST: str = ""  # Required in .env
    GLOBAL_DB_PORT: int = 3306
    GLOBAL_DB_NAME: str = ""  # Required in .env
    GLOBAL_DB_USER: str = ""  # Required in .env
    GLOBAL_DB_PASSWORD: str = ""  # Required in .env
    
    # Tenant Database
    TENANT_DB_HOST: str = ""  # Required in .env
    TENANT_DB_PORT: int = 3306
    TENANT_DB_NAME: str = ""  # Required in .env
    TENANT_DB_USER: str = ""  # Required in .env
    TENANT_DB_PASSWORD: str = ""  # Required in .env
    
    # JWT
    JWT_SECRET_KEY: str = ""  # Required in .env (min 32 chars)
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Security
    ARGON2_TIME_COST: int = 2
    ARGON2_MEMORY_COST: int = 65536
    ARGON2_PARALLELISM: int = 1
    RATE_LIMIT_PER_MINUTE: int = 100
    SESSION_TIMEOUT_MINUTES: int = 30
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"
    
    @property
    def global_db_url(self) -> str:
        """Construct global database URL for SQLAlchemy"""
        password = f":{self.GLOBAL_DB_PASSWORD}" if self.GLOBAL_DB_PASSWORD else ""
        return (
            f"mysql+aiomysql://{self.GLOBAL_DB_USER}{password}"
            f"@{self.GLOBAL_DB_HOST}:{self.GLOBAL_DB_PORT}/{self.GLOBAL_DB_NAME}"
        )
    
    @property
    def global_db_url_sync(self) -> str:
        """Construct global database URL for sync operations"""
        password = f":{self.GLOBAL_DB_PASSWORD}" if self.GLOBAL_DB_PASSWORD else ""
        return (
            f"mysql+pymysql://{self.GLOBAL_DB_USER}{password}"
            f"@{self.GLOBAL_DB_HOST}:{self.GLOBAL_DB_PORT}/{self.GLOBAL_DB_NAME}"
        )
    
    @property
    def tenant_db_url(self) -> str:
        """Construct tenant database URL for SQLAlchemy"""
        password = f":{self.TENANT_DB_PASSWORD}" if self.TENANT_DB_PASSWORD else ""
        return (
            f"mysql+aiomysql://{self.TENANT_DB_USER}{password}"
            f"@{self.TENANT_DB_HOST}:{self.TENANT_DB_PORT}/{self.TENANT_DB_NAME}"
        )
    
    @property
    def tenant_db_url_sync(self) -> str:
        """Construct tenant database URL for sync operations"""
        password = f":{self.TENANT_DB_PASSWORD}" if self.TENANT_DB_PASSWORD else ""
        return (
            f"mysql+pymysql://{self.TENANT_DB_USER}{password}"
            f"@{self.TENANT_DB_HOST}:{self.TENANT_DB_PORT}/{self.TENANT_DB_NAME}"
        )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Global settings instance
settings = get_settings()
