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
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import NullPool
from contextlib import contextmanager

from app.core.config import settings


# Declarative bases for each database
GlobalBase = declarative_base()
TenantBase = declarative_base()


class DatabaseManager:
    """
    Manages database connections for both Global and Tenant databases.
    Follows the pattern of lazy initialization to avoid connection issues.
    
    Supports dynamic tenant database connections based on tenant config.
    """
    
    def __init__(self):
        self._global_engine: AsyncEngine | None = None
        self._tenant_engine: AsyncEngine | None = None
        self._global_session_factory: async_sessionmaker | None = None
        self._tenant_session_factory: async_sessionmaker | None = None
        # Sync engines for Flask
        self._global_engine_sync = None
        self._global_session_factory_sync: sessionmaker | None = None
        # Dynamic tenant connections cache
        self._tenant_engines: dict[str, AsyncEngine] = {}
        self._tenant_engines_sync: dict[str, any] = {}
        self._tenant_session_factories: dict[str, async_sessionmaker] = {}
        self._tenant_session_factories_sync: dict[str, sessionmaker] = {}
    
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
    
    @property
    def global_engine_sync(self):
        """Lazy initialization of sync global database engine for Flask"""
        if self._global_engine_sync is None:
            self._global_engine_sync = create_engine(
                settings.global_db_url_sync,
                echo=settings.DEBUG,
                poolclass=NullPool,
                connect_args={"charset": "utf8mb4"}
            )
        return self._global_engine_sync
    
    @property
    def global_session_factory_sync(self) -> sessionmaker:
        """Sync session factory for Flask global database"""
        if self._global_session_factory_sync is None:
            self._global_session_factory_sync = sessionmaker(
                bind=self.global_engine_sync,
                expire_on_commit=False,
                autoflush=False
            )
        return self._global_session_factory_sync
    
    @contextmanager
    def get_global_session_sync(self):
        """Context manager for sync global database sessions (Flask)"""
        session = self.global_session_factory_sync()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
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
    
    # ── Dynamic Tenant Database Connections ──
    
    def get_tenant_engine_by_name(self, db_name: str) -> AsyncEngine:
        """
        Get or create an async engine for a specific tenant database.
        Engines are cached to avoid recreating connections.
        
        Args:
            db_name: Name of the tenant database (e.g., 'cliente_chacabuco')
        
        Returns:
            AsyncEngine for the specified database
        """
        if db_name not in self._tenant_engines:
            # Build tenant-specific database URL
            url = f"mysql+aiomysql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{db_name}"
            self._tenant_engines[db_name] = create_async_engine(
                url,
                echo=settings.DEBUG,
                poolclass=NullPool,
                connect_args={"charset": "utf8mb4"}
            )
        return self._tenant_engines[db_name]
    
    def get_tenant_engine_sync_by_name(self, db_name: str):
        """
        Get or create a sync engine for a specific tenant database (Flask).
        
        Args:
            db_name: Name of the tenant database (e.g., 'cliente_chacabuco')
        
        Returns:
            SQLAlchemy Engine for the specified database
        """
        if db_name not in self._tenant_engines_sync:
            # Build tenant-specific database URL
            url = f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{db_name}"
            self._tenant_engines_sync[db_name] = create_engine(
                url,
                echo=settings.DEBUG,
                poolclass=NullPool,
                connect_args={"charset": "utf8mb4"}
            )
        return self._tenant_engines_sync[db_name]
    
    def get_tenant_session_factory_by_name(self, db_name: str) -> async_sessionmaker:
        """Get or create async session factory for a tenant database"""
        if db_name not in self._tenant_session_factories:
            engine = self.get_tenant_engine_by_name(db_name)
            self._tenant_session_factories[db_name] = async_sessionmaker(
                bind=engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False
            )
        return self._tenant_session_factories[db_name]
    
    def get_tenant_session_factory_sync_by_name(self, db_name: str) -> sessionmaker:
        """Get or create sync session factory for a tenant database (Flask)"""
        if db_name not in self._tenant_session_factories_sync:
            engine = self.get_tenant_engine_sync_by_name(db_name)
            self._tenant_session_factories_sync[db_name] = sessionmaker(
                bind=engine,
                expire_on_commit=False,
                autoflush=False
            )
        return self._tenant_session_factories_sync[db_name]
    
    @asynccontextmanager
    async def get_tenant_session_by_name(self, db_name: str) -> AsyncGenerator[AsyncSession, None]:
        """
        Context manager for tenant database sessions with dynamic database selection.
        
        Args:
            db_name: Name of the tenant database (e.g., 'cliente_chacabuco')
        
        Usage:
            async with db_manager.get_tenant_session_by_name('cliente_chacabuco') as session:
                # Query tenant-specific data
                ...
        """
        factory = self.get_tenant_session_factory_by_name(db_name)
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    
    @contextmanager
    def get_tenant_session_sync_by_name(self, db_name: str):
        """
        Context manager for sync tenant database sessions (Flask).
        
        Args:
            db_name: Name of the tenant database (e.g., 'cliente_chacabuco')
        """
        factory = self.get_tenant_session_factory_sync_by_name(db_name)
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    
    async def close(self):
        """Close all database connections"""
        if self._global_engine:
            await self._global_engine.dispose()
        if self._tenant_engine:
            await self._tenant_engine.dispose()
        
        # Close dynamic tenant engines
        for engine in self._tenant_engines.values():
            await engine.dispose()
        
        # Close sync engines
        if self._global_engine_sync:
            self._global_engine_sync.dispose()
        
        for engine in self._tenant_engines_sync.values():
            engine.dispose()


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
