"""
DatabaseManager — Sync-only connection management.

Key design decisions:
- NullPool: cPanel limits simultaneous connections.
  Each request opens/closes its own connection.
- Lazy engines: created on first use, not at import time.
- Sync only: Phase 2 uses sync engines (Flask + sync cache load).
  Async engines will be added in a future phase if needed.
"""

import logging
from contextlib import contextmanager
from typing import Dict, Generator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from dashboard_saas.core.config import settings

logger = logging.getLogger(__name__)

# Common engine kwargs for every connection
_ENGINE_KWARGS = {
    "poolclass": NullPool,
    "connect_args": {"charset": "utf8mb4"},
}


class DatabaseManager:
    """
    Centralised database connection manager (sync only).

    Responsibilities:
    - Global DB engine (for camet_global).
    - Dynamic tenant engines resolved at runtime by db_name.
    - Context-managed sessions with auto-commit/rollback.
    """

    def __init__(self) -> None:
        # Global DB
        self._global_engine: Optional[Engine] = None
        self._global_session_factory: Optional[sessionmaker] = None

        # Dynamic tenant engines: db_name → engine / session factory
        self._tenant_engines: Dict[str, Engine] = {}
        self._tenant_session_factories: Dict[str, sessionmaker] = {}

    # ─────────────────────────────────────────────────────────────
    #  GLOBAL DB
    # ─────────────────────────────────────────────────────────────

    @property
    def global_engine(self) -> Engine:
        """Lazy-create sync engine for the global database."""
        if self._global_engine is None:
            self._global_engine = create_engine(
                settings.global_db_url_sync,
                echo=settings.DEBUG,
                **_ENGINE_KWARGS,
            )
            logger.info("Created global DB engine (%s)", settings.GLOBAL_DB_NAME)
        return self._global_engine

    @property
    def global_session_factory(self) -> sessionmaker:
        if self._global_session_factory is None:
            self._global_session_factory = sessionmaker(
                bind=self.global_engine,
                expire_on_commit=False,
                autoflush=False,
            )
        return self._global_session_factory

    # ─────────────────────────────────────────────────────────────
    #  DYNAMIC TENANT DB
    # ─────────────────────────────────────────────────────────────

    def _get_or_create_engine(self, db_name: str) -> Engine:
        """Get (or lazily create) a sync engine for a tenant DB."""
        if db_name not in self._tenant_engines:
            url = settings.tenant_db_url_for(db_name)
            self._tenant_engines[db_name] = create_engine(
                url, echo=settings.DEBUG, **_ENGINE_KWARGS,
            )
            logger.info("Created tenant DB engine (%s)", db_name)
        return self._tenant_engines[db_name]

    def _get_or_create_session_factory(self, db_name: str) -> sessionmaker:
        if db_name not in self._tenant_session_factories:
            engine = self._get_or_create_engine(db_name)
            self._tenant_session_factories[db_name] = sessionmaker(
                bind=engine,
                expire_on_commit=False,
                autoflush=False,
            )
        return self._tenant_session_factories[db_name]

    # ─────────────────────────────────────────────────────────────
    #  SESSION CONTEXT MANAGERS
    # ─────────────────────────────────────────────────────────────

    @contextmanager
    def get_global_session(self) -> Generator[Session, None, None]:
        """Sync session for camet_global."""
        session: Session = self.global_session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @contextmanager
    def get_tenant_session(self, db_name: str) -> Generator[Session, None, None]:
        """Sync session for a tenant DB by name."""
        factory = self._get_or_create_session_factory(db_name)
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
    #  CONNECTIVITY TEST
    # ─────────────────────────────────────────────────────────────

    def test_connection(self, db_name: str) -> bool:
        """Test if a database connection works. Returns True/False."""
        try:
            engine = self._get_or_create_engine(db_name)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error("Connection test failed for %s: %s", db_name, e)
            return False

    # ─────────────────────────────────────────────────────────────
    #  CLEANUP
    # ─────────────────────────────────────────────────────────────

    def close_all(self) -> None:
        """Dispose of every engine on shutdown."""
        if self._global_engine:
            self._global_engine.dispose()
            logger.info("Disposed global DB engine")

        for db_name, engine in self._tenant_engines.items():
            engine.dispose()
            logger.info("Disposed tenant DB engine (%s)", db_name)

        self._tenant_engines.clear()
        self._tenant_session_factories.clear()


# ── Global singleton ─────────────────────────────────────────────
db_manager = DatabaseManager()
