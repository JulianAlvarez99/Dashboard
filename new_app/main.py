"""
FastAPI application factory + lifespan.

This is the **data engine** of the SaaS platform:
- REST API for dashboard data, filters, widgets, layout.
- MetadataCache loaded at startup.
- CORS configured for Flask frontend.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from new_app.core.cache import metadata_cache
from new_app.core.config import settings
from new_app.core.database import db_manager
from new_app.api.v1 import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: ready the engine (cache is loaded on-demand after login).
    Shutdown: close DB connections.
    """
    print("🚀 Starting Camet Analytics API …")
    print("ℹ️  MetadataCache will load after first tenant login")

    yield

    print("🛑 Shutting down API …")
    metadata_cache.clear()
    await db_manager.close()
    print("✅ DB connections closed")


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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5000",
            "http://127.0.0.1:5000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    @app.get("/")
    async def root():
        return {
            "app": settings.APP_NAME,
            "version": "2.0.0",
            "status": "running",
            "docs": "/api/docs" if settings.DEBUG else "disabled",
        }

    return app


# Module-level instance for ``uvicorn new_app.main:app``
app = create_fastapi_app()
