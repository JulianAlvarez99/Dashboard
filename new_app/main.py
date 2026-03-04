"""
FastAPI application factory + lifespan.

This is the **data engine** of the SaaS platform:
- REST API for dashboard data, filters, widgets, layout.
- MetadataCache loaded at startup.
- CORS configured for Flask frontend.
"""

import logging
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from new_app.core.cache import metadata_cache
from new_app.core.config import settings
from new_app.core.database import db_manager
from new_app.core.fastapi_limiter import RateLimitMiddleware
from new_app.api.v1 import api_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: ready the engine (cache is loaded on-demand after login).
    Shutdown: close DB connections.
    """
    logger.info("Starting Camet Analytics API")
    logger.info("MetadataCache will load after first tenant login")

    yield

    logger.info("Shutting down API")
    metadata_cache.clear()
    await db_manager.close()
    logger.info("DB connections closed")


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

    # ── Security headers middleware ──────────────────────────
    class SecurityHeadersMiddleware(BaseHTTPMiddleware):
        """Inject hardening headers on every FastAPI response."""
        async def dispatch(self, request: Request, call_next) -> Response:
            response = await call_next(request)
            response.headers.setdefault("X-Frame-Options", "DENY")
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("X-XSS-Protection", "1; mode=block")
            response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
            response.headers.setdefault(
                "Permissions-Policy",
                "geolocation=(), microphone=(), camera=(), interest-cohort=()",
            )
            return response

    app.add_middleware(SecurityHeadersMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    # Rate limiting — sliding-window per IP.
    # Executes before CORS (outermost, registered last).
    app.add_middleware(RateLimitMiddleware)

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Catch-all: log the full traceback and return a safe error response."""
        logger.error(
            "Unhandled exception on %s %s\n%s",
            request.method,
            request.url.path,
            traceback.format_exc(),
        )
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"},
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

