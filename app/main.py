"""
FastAPI Application Entry Point
Handles API endpoints and serves as the data layer
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.cache import metadata_cache
from app.core.database import db_manager
from app.api.v1 import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Runs on startup and shutdown.
    """
    # Startup
    print("🚀 Starting Dashboard SaaS API...")
    
    # Load metadata cache
    try:
        await metadata_cache.load_all()
        print("✅ Metadata cache loaded successfully")
        print(f"   Cache info: {metadata_cache.get_cache_info()}")
    except Exception as e:
        print(f"⚠️ Warning: Could not load metadata cache: {e}")
        print("   API will start but some features may not work")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down Dashboard SaaS API...")
    await db_manager.close()
    print("✅ Database connections closed")


def create_app() -> FastAPI:
    """
    Application factory for FastAPI.
    """
    app = FastAPI(
        title="Dashboard SaaS Industrial API",
        description="API for industrial production dashboard with configuration-driven UI",
        version="2.0.0",
        lifespan=lifespan,
        docs_url="/api/docs" if settings.DEBUG else None,
        redoc_url="/api/redoc" if settings.DEBUG else None,
    )
    
    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5000", "http://127.0.0.1:5000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include API router
    app.include_router(api_router)
    
    # Root endpoint
    @app.get("/")
    async def root():
        return {
            "app": settings.APP_NAME,
            "version": "2.0.0",
            "status": "running",
            "docs": "/api/docs" if settings.DEBUG else "disabled"
        }
    
    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
