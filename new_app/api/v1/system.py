"""System endpoints — health check, cache info, cache refresh."""

import secrets
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from new_app.core.cache import metadata_cache
from new_app.core.config import settings

router = APIRouter(prefix="/system", tags=["system"])


def require_internal_key(x_internal_key: str = Header(...)) -> None:
    """
    Dependency: validate the X-Internal-Key header.

    Only internal callers (e.g. Flask login handler) should know
    this key.  Protects cache load/refresh from unauthenticated use.
    """
    if not secrets.compare_digest(x_internal_key, settings.API_INTERNAL_KEY):
        raise HTTPException(status_code=401, detail="Invalid internal key")


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
async def cache_load(
    db_name: str,
    _: None = Depends(require_internal_key),
):
    """Load cache for a specific tenant (called after login)."""
    await metadata_cache.load_for_tenant(db_name)
    return {
        "status": "loaded",
        "tenant": db_name,
        "info": metadata_cache.get_cache_info(),
    }


@router.post("/cache/refresh")
async def cache_refresh(
    db_name: Optional[str] = None,
    _: None = Depends(require_internal_key),
):
    """Force-reload all cached metadata."""
    try:
        await metadata_cache.refresh(db_name)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "status": "refreshed",
        "info": metadata_cache.get_cache_info(),
    }
