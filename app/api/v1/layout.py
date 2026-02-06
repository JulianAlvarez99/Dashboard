"""
Layout API Endpoints
Provides dashboard layout configuration based on tenant and role
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from app.core.database import db_manager
from app.services.config.layout_service import LayoutService
from app.core.cache import metadata_cache


router = APIRouter(prefix="/layout", tags=["Layout"])


@router.get("/config")
async def get_layout_config(
    tenant_id: int = Query(..., description="Tenant ID"),
    role: str = Query(..., description="User role (ADMIN, MANAGER, VIEWER)")
):
    """
    Get dashboard layout configuration for a tenant and role.
    
    Returns the layout_config from DASHBOARD_TEMPLATE table,
    along with resolved widget and filter metadata.
    """
    async with db_manager.get_global_session() as session:
        layout = await LayoutService.get_layout_config(session, tenant_id, role)
        
        if layout is None:
            raise HTTPException(
                status_code=404,
                detail=f"No layout configuration found for tenant {tenant_id} with role {role}"
            )
        
        # Resolve widgets and filters from cache
        widgets = LayoutService.resolve_widgets_from_cache(layout.enabled_widget_ids)
        filters = LayoutService.resolve_filters_from_cache(layout.enabled_filter_ids)
        
        return {
            "tenant_id": layout.tenant_id,
            "role": layout.role,
            "widgets": [w.to_dict() for w in widgets],
            "filters": [f.to_dict() for f in filters],
            "raw_config": layout.raw_config
        }


@router.get("/widgets")
async def get_enabled_widgets(
    tenant_id: int = Query(..., description="Tenant ID"),
    role: str = Query(..., description="User role")
):
    """
    Get only the enabled widgets for a tenant/role layout.
    """
    async with db_manager.get_global_session() as session:
        layout = await LayoutService.get_layout_config(session, tenant_id, role)
        
        if layout is None:
            return {"widgets": [], "count": 0}
        
        widgets = LayoutService.resolve_widgets_from_cache(layout.enabled_widget_ids)
        
        return {
            "widgets": [w.to_dict() for w in widgets],
            "count": len(widgets)
        }


@router.get("/filters")
async def get_enabled_filters(
    tenant_id: int = Query(..., description="Tenant ID"),
    role: str = Query(..., description="User role")
):
    """
    Get only the enabled filters for a tenant/role layout.
    """
    async with db_manager.get_global_session() as session:
        layout = await LayoutService.get_layout_config(session, tenant_id, role)
        
        if layout is None:
            return {"filters": [], "count": 0}
        
        filters = LayoutService.resolve_filters_from_cache(layout.enabled_filter_ids)
        
        return {
            "filters": [f.to_dict() for f in filters],
            "count": len(filters)
        }
