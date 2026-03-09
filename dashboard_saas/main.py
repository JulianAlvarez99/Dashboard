"""
FastAPI application — Data engine.

Phase 2: system endpoints + cache warmup on startup.
"""

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dashboard_saas.core.config import settings

logger = logging.getLogger(__name__)


def _warmup_cache():
    """
    Load the metadata cache in a background thread at startup.

    Uses DEFAULT_DB_NAME from .env so the cache is ready
    before any request arrives.
    """
    db_name = settings.DEFAULT_DB_NAME
    if not db_name:
        logger.warning("DEFAULT_DB_NAME not set — skipping cache warmup")
        return

    try:
        from dashboard_saas.services.cache_service import CacheService
        result = CacheService.load_for_tenant(db_name)
        logger.info("Cache warmup complete: %s", result.get("status"))
    except Exception as e:
        logger.error("Cache warmup failed: %s", e, exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks."""
    logger.info("Starting Camet Analytics API (Phase 2)")

    # Warmup cache in a background thread (sync DB calls)
    warmup = threading.Thread(target=_warmup_cache, name="cache-warmup", daemon=True)
    warmup.start()

    yield

    # Cleanup
    from dashboard_saas.core.database import db_manager
    db_manager.close_all()
    logger.info("Shutting down API — all DB engines disposed")


def create_fastapi_app() -> FastAPI:
    """Application factory for FastAPI."""
    app = FastAPI(
        title="Camet Analytics API",
        description="REST API for industrial dashboard SaaS",
        version="2.0.0",
        lifespan=lifespan,
        docs_url="/api/docs" if settings.DEBUG else None,
        redoc_url="/api/redoc" if settings.DEBUG else None,
    )

    # ── CORS ────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    # ── API Routers ─────────────────────────────────────────────
    from dashboard_saas.api.v1.system import router as system_router
    from dashboard_saas.api.v1.dashboard import router as dashboard_router
    app.include_router(system_router)
    app.include_router(dashboard_router)

    # ── Root info ───────────────────────────────────────────────
    @app.get("/")
    async def root():
        return {
            "app": settings.APP_NAME,
            "version": "2.0.0",
            "status": "running",
            "docs": "/api/docs" if settings.DEBUG else "disabled",
        }

    # ── Simple /health (backward compat with Phase 1) ───────────
    @app.get("/health")
    async def health_simple():
        return {"status": "ok"}

    return app


# Module-level instance for `uvicorn dashboard_saas.main:app`
app = create_fastapi_app()
