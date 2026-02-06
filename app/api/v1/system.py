"""
System API Endpoints
Health checks, cache management, and system info
"""

from typing import Dict, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.cache import metadata_cache
from app.core.config import settings


router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    environment: str
    cache_loaded: bool


class CacheInfoResponse(BaseModel):
    """Cache statistics response"""
    is_loaded: bool
    tables: Dict[str, Any]


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    
    Returns basic system health information.
    """
    return HealthResponse(
        status="healthy",
        version="2.0.0",
        environment=settings.APP_ENV,
        cache_loaded=metadata_cache.is_loaded
    )


@router.get("/cache/info", response_model=CacheInfoResponse)
async def get_cache_info():
    """
    Get cache statistics.
    
    Shows what's loaded in the metadata cache and when.
    """
    return CacheInfoResponse(
        is_loaded=metadata_cache.is_loaded,
        tables=metadata_cache.get_cache_info()
    )


@router.post("/cache/refresh")
async def refresh_cache():
    """
    Force refresh of metadata cache.
    
    Reloads all metadata from databases.
    """
    await metadata_cache.refresh()
    return {
        "status": "success",
        "message": "Cache refreshed",
        "info": metadata_cache.get_cache_info()
    }


@router.get("/config")
async def get_app_config():
    """
    Get non-sensitive application configuration.
    
    Useful for debugging.
    """
    return {
        "app_name": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "debug": settings.DEBUG,
        "api_base_url": settings.API_BASE_URL,
        "global_db_name": settings.GLOBAL_DB_NAME,
        "tenant_db_name": settings.TENANT_DB_NAME
    }
