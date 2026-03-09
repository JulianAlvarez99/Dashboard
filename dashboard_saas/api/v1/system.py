"""
System endpoints — Health, cache management.

Phase 2: Exposes cache status and loading endpoints.
"""

import logging

from fastapi import APIRouter, HTTPException

from dashboard_saas.core.cache import metadata_cache
from dashboard_saas.core.config import settings
from dashboard_saas.services.cache_service import CacheService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/health")
async def health():
    """Application health check."""
    return {
        "status": "ok",
        "cache_loaded": metadata_cache.is_loaded,
        "current_tenant": metadata_cache.current_tenant,
    }


@router.post("/cache/load")
async def cache_load(db_name: str = None):
    """
    Load (or reload) the metadata cache for a tenant.

    If db_name is not provided, uses DEFAULT_DB_NAME from .env.
    """
    target = db_name or settings.DEFAULT_DB_NAME
    if not target:
        raise HTTPException(
            status_code=400,
            detail="No db_name provided and DEFAULT_DB_NAME is not set in .env"
        )

    try:
        result = CacheService.load_for_tenant(target)
        return result
    except Exception as e:
        logger.error("Cache load failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Cache load failed: {str(e)}")


@router.get("/cache/status")
async def cache_status():
    """Return cache status and table counts."""
    return metadata_cache.get_cache_info()


@router.post("/cache/refresh")
async def cache_refresh():
    """Force-reload the cache for the current tenant."""
    try:
        result = CacheService.refresh()
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Cache refresh failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Cache refresh failed: {str(e)}")
