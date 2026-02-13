"""
DatabaseManager — Dual sync/async connection management.

Key design decisions:
- NullPool everywhere: cPanel shared hosting limits simultaneous connections.
  Each request opens/closes its own connection — higher latency per request
  but zero risk of exhausting the connection limit.
- Lazy engines: Created on first use, not at import time.
- Dynamic tenants: `get_tenant_session_by_name(db_name)` supports true
  multi-tenancy where the db_name is resolved from tenant.config_tenant
  at login time.
"""

from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator, Dict, Optional

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import NullPool

from new_app.core.config import settings


# ── Declarative bases — one per physical database ────────────────
GlobalBase = declarative_base()
TenantBase = declarative_base()

# Common engine kwargs for every connection
_ENGINE_KWARGS = {
    "poolclass": NullPool,
    "connect_args": {"charset": "utf8mb4"},
}


class DatabaseManager:
    """
    Centralised database connection manager.

    Responsibilities:
    - Global DB engines (async for FastAPI, sync for Flask).
    - Default tenant DB engine (from .env TENANT_DB_NAME).
    - Dynamic tenant engines resolved at runtime by db_name.
    - Context-managed sessions with auto-commit/rollback.
    """

    def __init__(self) -> None:
        # Global
        self._global_engine: Optional[AsyncEngine] = None
        self._global_session_factory: Optional[async_sessionmaker] = None
        self._global_engine_sync = None
        self._global_session_factory_sync: Optional[sessionmaker] = None

        # Default tenant (from .env)
        self._tenant_engine: Optional[AsyncEngine] = None
        self._tenant_session_factory: Optional[async_sessionmaker] = None

        # Dynamic tenants cache: db_name → engine / factory
        self._tenant_engines: Dict[str, AsyncEngine] = {}
        self._tenant_engines_sync: Dict[str, object] = {}
        self._tenant_session_factories: Dict[str, async_sessionmaker] = {}
        self._tenant_session_factories_sync: Dict[str, sessionmaker] = {}

    # ─────────────────────────────────────────────────────────────
    #  GLOBAL DB
    # ─────────────────────────────────────────────────────────────

    @property
    def global_engine(self) -> AsyncEngine:
        if self._global_engine is None:
            self._global_engine = create_async_engine(
                settings.global_db_url,
                echo=settings.DEBUG,
                **_ENGINE_KWARGS,
            )
        return self._global_engine

    @property
    def global_session_factory(self) -> async_sessionmaker:
        if self._global_session_factory is None:
            self._global_session_factory = async_sessionmaker(
                bind=self.global_engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
            )
        return self._global_session_factory

    @property
    def global_engine_sync(self):
        if self._global_engine_sync is None:
            self._global_engine_sync = create_engine(
                settings.global_db_url_sync,
                echo=settings.DEBUG,
                **_ENGINE_KWARGS,
            )
        return self._global_engine_sync

    @property
    def global_session_factory_sync(self) -> sessionmaker:
        if self._global_session_factory_sync is None:
            self._global_session_factory_sync = sessionmaker(
                bind=self.global_engine_sync,
                expire_on_commit=False,
                autoflush=False,
            )
        return self._global_session_factory_sync

    # ─────────────────────────────────────────────────────────────
    #  DEFAULT TENANT DB (from .env)
    # ─────────────────────────────────────────────────────────────

    @property
    def tenant_engine(self) -> AsyncEngine:
        if self._tenant_engine is None:
            self._tenant_engine = create_async_engine(
                settings.tenant_db_url,
                echo=settings.DEBUG,
                **_ENGINE_KWARGS,
            )
        return self._tenant_engine

    @property
    def tenant_session_factory(self) -> async_sessionmaker:
        if self._tenant_session_factory is None:
            self._tenant_session_factory = async_sessionmaker(
                bind=self.tenant_engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
            )
        return self._tenant_session_factory

    # ─────────────────────────────────────────────────────────────
    #  DYNAMIC TENANT DB (resolved at runtime)
    # ─────────────────────────────────────────────────────────────

    def _get_or_create_engine(self, db_name: str) -> AsyncEngine:
        """Get (or lazily create) an async engine for a tenant DB."""
        if db_name not in self._tenant_engines:
            url = settings.tenant_db_url_for(db_name, driver="aiomysql")
            self._tenant_engines[db_name] = create_async_engine(
                url, echo=settings.DEBUG, **_ENGINE_KWARGS,
            )
        return self._tenant_engines[db_name]

    def _get_or_create_engine_sync(self, db_name: str):
        """Get (or lazily create) a sync engine for a tenant DB."""
        if db_name not in self._tenant_engines_sync:
            url = settings.tenant_db_url_for(db_name, driver="pymysql")
            self._tenant_engines_sync[db_name] = create_engine(
                url, echo=settings.DEBUG, **_ENGINE_KWARGS,
            )
        return self._tenant_engines_sync[db_name]

    def _get_or_create_session_factory(self, db_name: str) -> async_sessionmaker:
        if db_name not in self._tenant_session_factories:
            engine = self._get_or_create_engine(db_name)
            self._tenant_session_factories[db_name] = async_sessionmaker(
                bind=engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
            )
        return self._tenant_session_factories[db_name]

    def _get_or_create_session_factory_sync(self, db_name: str) -> sessionmaker:
        if db_name not in self._tenant_session_factories_sync:
            engine = self._get_or_create_engine_sync(db_name)
            self._tenant_session_factories_sync[db_name] = sessionmaker(
                bind=engine,
                expire_on_commit=False,
                autoflush=False,
            )
        return self._tenant_session_factories_sync[db_name]

    # ─────────────────────────────────────────────────────────────
    #  SESSION CONTEXT MANAGERS
    # ─────────────────────────────────────────────────────────────

    @asynccontextmanager
    async def get_global_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Async session for camet_global (FastAPI)."""
        async with self.global_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    @contextmanager
    def get_global_session_sync(self):
        """Sync session for camet_global (Flask)."""
        session: Session = self.global_session_factory_sync()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @asynccontextmanager
    async def get_tenant_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Async session for default tenant DB (from .env)."""
        async with self.tenant_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    @asynccontextmanager
    async def get_tenant_session_by_name(
        self, db_name: str
    ) -> AsyncGenerator[AsyncSession, None]:
        """Async session for an arbitrary tenant DB (multi-tenant)."""
        factory = self._get_or_create_session_factory(db_name)
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    @contextmanager
    def get_tenant_session_sync_by_name(self, db_name: str):
        """Sync session for an arbitrary tenant DB (Flask multi-tenant)."""
        factory = self._get_or_create_session_factory_sync(db_name)
        session: Session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # ─────────────────────────────────────────────────────────────
    #  CLEANUP
    # ─────────────────────────────────────────────────────────────

    async def close(self) -> None:
        """Dispose of every engine on shutdown."""
        engines_async = [self._global_engine, self._tenant_engine]
        engines_async += list(self._tenant_engines.values())
        for engine in engines_async:
            if engine:
                await engine.dispose()

        engines_sync = [self._global_engine_sync]
        engines_sync += list(self._tenant_engines_sync.values())
        for engine in engines_sync:
            if engine:
                engine.dispose()


# ── Global singleton ─────────────────────────────────────────────
db_manager = DatabaseManager()


# ── FastAPI dependency injection ─────────────────────────────────
async def get_global_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Depends() for camet_global."""
    async with db_manager.get_global_session() as session:
        yield session


async def get_tenant_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Depends() for the default tenant DB."""
    async with db_manager.get_tenant_session() as session:
        yield session
