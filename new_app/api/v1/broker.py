"""
Broker API — Diagnostic & admin endpoints for external APIs.

Provides visibility into:
  - Configured external API sources and their status.
  - On-demand test connectivity for specific APIs.
  - Cache management for external API responses.
"""

from fastapi import APIRouter, HTTPException

from new_app.services.broker.api_config import api_config_loader
from new_app.services.broker.external_api_service import external_api_service

router = APIRouter(prefix="/broker", tags=["broker"])


@router.get("/apis")
async def list_apis():
    """
    List all configured external API sources.

    Returns enabled and disabled APIs with their metadata.
    """
    all_endpoints = api_config_loader.get_all()
    return {
        "total": len(all_endpoints),
        "apis": [
            {
                "api_id": ep.api_id,
                "name": ep.name,
                "base_url": ep.base_url,
                "method": ep.method,
                "timeout": ep.timeout,
                "auth_type": ep.auth_type,
                "cache_ttl": ep.cache_ttl,
                "enabled": ep.enabled,
            }
            for ep in all_endpoints.values()
        ],
    }


@router.get("/apis/enabled")
async def list_enabled_apis():
    """List only enabled external API sources."""
    return {
        "apis": external_api_service.list_available(),
    }


@router.get("/apis/{api_id}")
async def get_api_detail(api_id: str):
    """
    Get full configuration for a specific API source.

    Does NOT execute the request — use ``/test/{api_id}`` for that.
    """
    endpoint = api_config_loader.get(api_id)
    if endpoint is None:
        raise HTTPException(status_code=404, detail=f"API '{api_id}' not found")

    return {
        "api_id": endpoint.api_id,
        "name": endpoint.name,
        "base_url": endpoint.base_url,
        "method": endpoint.method,
        "timeout": endpoint.timeout,
        "auth_type": endpoint.auth_type,
        "has_auth_env_var": bool(endpoint.auth_env_var),
        "headers": list(endpoint.headers.keys()),
        "params": list(endpoint.params.keys()),
        "response_key": endpoint.response_key,
        "cache_ttl": endpoint.cache_ttl,
        "enabled": endpoint.enabled,
    }


@router.post("/test/{api_id}")
async def test_api(api_id: str):
    """
    Execute a live test request to an external API.

    Returns the raw result (ok, status, data preview, error).
    Bypasses the TTL cache.
    """
    endpoint = api_config_loader.get(api_id)
    if endpoint is None:
        raise HTTPException(status_code=404, detail=f"API '{api_id}' not found")

    if not endpoint.enabled:
        raise HTTPException(
            status_code=400,
            detail=f"API '{api_id}' is disabled — enable it in external_apis.yml first",
        )

    result = await external_api_service.fetch(api_id, bypass_cache=True)

    # Truncate data for preview
    data_preview = result.get("data")
    if isinstance(data_preview, list) and len(data_preview) > 5:
        data_preview = data_preview[:5]
        truncated = True
    else:
        truncated = False

    return {
        "api_id": api_id,
        "ok": result["ok"],
        "status": result.get("status", 0),
        "error": result.get("error"),
        "data_preview": data_preview,
        "truncated": truncated,
    }


@router.post("/cache/clear")
async def clear_cache(api_id: str | None = None):
    """
    Clear the external API response cache.

    If ``api_id`` is provided, clear only that key.
    Otherwise clear all cached responses.
    """
    external_api_service.clear_cache(api_id)
    return {
        "status": "cleared",
        "scope": api_id or "all",
    }


@router.post("/config/reload")
async def reload_config():
    """
    Re-read ``external_apis.yml`` from disk.

    Use after editing the YAML file to pick up changes
    without restarting the server.
    """
    api_config_loader.reload()
    external_api_service.clear_cache()

    return {
        "status": "reloaded",
        "total_apis": len(api_config_loader.list_ids()),
        "enabled_count": len(api_config_loader.get_enabled()),
    }
