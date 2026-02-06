"""
Database connection management for Global and Tenant databases
Uses SQLAlchemy async engine for FastAPI endpoints
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

from app.core.config import settings


# Declarative bases for each database
GlobalBase = declarative_base()
TenantBase = declarative_base()


class DatabaseManager:
    """
    Manages database connections for both Global and Tenant databases.
    Follows the pattern of lazy initialization to avoid connection issues.
    """
    
    def __init__(self):
        self._global_engine: AsyncEngine | None = None
        self._tenant_engine: AsyncEngine | None = None
        self._global_session_factory: async_sessionmaker | None = None
        self._tenant_session_factory: async_sessionmaker | None = None
    
    @property
    def global_engine(self) -> AsyncEngine:
        """Lazy initialization of global database engine"""
        if self._global_engine is None:
            self._global_engine = create_async_engine(
                settings.global_db_url,
                echo=settings.DEBUG,
                poolclass=NullPool,  # For serverless/cPanel compatibility
                connect_args={"charset": "utf8mb4"}
            )
        return self._global_engine
    
    @property
    def tenant_engine(self) -> AsyncEngine:
        """Lazy initialization of tenant database engine"""
        if self._tenant_engine is None:
            self._tenant_engine = create_async_engine(
                settings.tenant_db_url,
                echo=settings.DEBUG,
                poolclass=NullPool,
                connect_args={"charset": "utf8mb4"}
            )
        return self._tenant_engine
    
    @property
    def global_session_factory(self) -> async_sessionmaker:
        """Session factory for global database"""
        if self._global_session_factory is None:
            self._global_session_factory = async_sessionmaker(
                bind=self.global_engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False
            )
        return self._global_session_factory
    
    @property
    def tenant_session_factory(self) -> async_sessionmaker:
        """Session factory for tenant database"""
        if self._tenant_session_factory is None:
            self._tenant_session_factory = async_sessionmaker(
                bind=self.tenant_engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False
            )
        return self._tenant_session_factory
    
    @asynccontextmanager
    async def get_global_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Context manager for global database sessions"""
        async with self.global_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    
    @asynccontextmanager
    async def get_tenant_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Context manager for tenant database sessions"""
        async with self.tenant_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    
    async def close(self):
        """Close all database connections"""
        if self._global_engine:
            await self._global_engine.dispose()
        if self._tenant_engine:
            await self._tenant_engine.dispose()


# Global database manager instance
db_manager = DatabaseManager()


# Dependency functions for FastAPI
async def get_global_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for global database session"""
    async with db_manager.get_global_session() as session:
        yield session


async def get_tenant_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for tenant database session"""
    async with db_manager.get_tenant_session() as session:
        yield session
