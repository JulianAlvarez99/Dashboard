"""
Layout API — Dashboard layout resolution from ``dashboard_template``.

Routes:
  GET /layout/config?tenant_id=X&role=Y  → full layout (widgets + filter IDs)
  GET /layout/widgets?tenant_id=X&role=Y → only resolved widgets
  GET /layout/filters?tenant_id=X&role=Y → only enabled filter IDs
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from new_app.core.cache import metadata_cache
from new_app.services.config.layout_service import layout_service

router = APIRouter(prefix="/layout", tags=["layout"])


def _check_cache():
    if not metadata_cache.is_loaded:
        raise HTTPException(status_code=503, detail="Cache not loaded — log in first")


@router.get("/config")
async def get_layout_config(
    tenant_id: int = Query(..., description="Tenant ID"),
    role: str = Query(..., description="User role (ADMIN, MANAGER, VIEWER)"),
):
    """
    Full resolved layout for a tenant + role.

    Returns widgets metadata + enabled filter/widget IDs from
    ``dashboard_template.layout_config``.
    """
    _check_cache()

    result = await layout_service.get_resolved_layout(tenant_id, role)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No dashboard template for tenant_id={tenant_id}, role={role}",
        )
    return result


@router.get("/widgets")
async def get_layout_widgets(
    tenant_id: int = Query(..., description="Tenant ID"),
    role: str = Query(..., description="User role"),
):
    """Return only the resolved widget list for a tenant + role."""
    _check_cache()

    result = await layout_service.get_resolved_layout(tenant_id, role)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No dashboard template for tenant_id={tenant_id}, role={role}",
        )
    return result["widgets"]


@router.get("/filters")
async def get_layout_filter_ids(
    tenant_id: int = Query(..., description="Tenant ID"),
    role: str = Query(..., description="User role"),
):
    """Return the enabled filter IDs for a tenant + role."""
    _check_cache()

    config = await layout_service.get_layout_config(tenant_id, role)
    if config is None:
        raise HTTPException(
            status_code=404,
            detail=f"No dashboard template for tenant_id={tenant_id}, role={role}",
        )
    return {"enabled_filter_ids": config.enabled_filter_ids}
