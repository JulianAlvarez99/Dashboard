"""System endpoints — health check, cache info, cache refresh."""

from typing import Optional

from fastapi import APIRouter, HTTPException

from new_app.core.cache import metadata_cache

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health")
async def health_check():
    """Basic liveness probe."""
    return {
        "status": "ok",
        "cache_loaded": metadata_cache.is_loaded,
        "current_tenant": metadata_cache.current_tenant,
    }


@router.get("/cache/info")
async def cache_info():
    """Return cache statistics (table counts, load times)."""
    if not metadata_cache.is_loaded:
        return {"current_tenant": None, "tables": {}, "message": "No tenant loaded yet"}
    return metadata_cache.get_cache_info()


@router.post("/cache/load/{db_name}")
async def cache_load(db_name: str):
    """Load cache for a specific tenant (called after login)."""
    await metadata_cache.load_for_tenant(db_name)
    return {
        "status": "loaded",
        "tenant": db_name,
        "info": metadata_cache.get_cache_info(),
    }


@router.post("/cache/refresh")
async def cache_refresh(db_name: Optional[str] = None):
    """Force-reload all cached metadata."""
    try:
        await metadata_cache.refresh(db_name)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "status": "refreshed",
        "info": metadata_cache.get_cache_info(),
    }
