"""
Dashboard API Endpoints
Single-query data pipeline for the dashboard.

Core endpoint: /api/v1/dashboard/data
- Receives all filter parameters
- Executes ONE query per production line
- Enriches data with pandas using MetadataCache
- Processes all widgets from the enriched DataFrame
- Returns all widget data in a single response
"""

from datetime import date
from typing import Dict, List, Any, Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_tenant_db
from app.core.cache import metadata_cache
from app.services.dashboard_data_service import DashboardDataService
from app.services.widgets.base import FilterParams


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# === Pydantic Models ===

class DashboardDataRequest(BaseModel):
    """Request parameters for dashboard data"""
    widget_ids: List[int]
    line_id: Optional[int] = None
    line_ids: Optional[str] = None  # Comma-separated
    area_ids: Optional[str] = None
    product_ids: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    shift_id: Optional[int] = None
    interval: str = "hour"
    curve_type: str = "smooth"


class WidgetDataItem(BaseModel):
    """Individual widget data"""
    widget_id: int
    widget_name: str
    widget_type: str
    data: Any
    metadata: Dict[str, Any]


class DashboardDataResponse(BaseModel):
    """Complete dashboard data response"""
    widgets: Dict[str, Any]
    metadata: Dict[str, Any]


# === Endpoints ===

@router.post("/data", response_model=DashboardDataResponse)
async def get_dashboard_data(
    request: DashboardDataRequest,
    session: AsyncSession = Depends(get_tenant_db)
):
    """
    Get all widget data in a single request.
    
    This is the primary endpoint for the dashboard. It:
    1. Fetches raw detections with ONE SQL query per production line
    2. Enriches data using MetadataCache (application-side joins)
    3. Processes each widget from the enriched DataFrame
    4. Returns all widget data at once
    
    This approach avoids N+1 queries and expensive database JOINs.
    """
    if not request.widget_ids:
        raise HTTPException(status_code=400, detail="widget_ids is required")

    # Build FilterParams from request
    params = FilterParams.from_dict({
        "line_id": request.line_id,
        "line_ids": request.line_ids,
        "area_ids": request.area_ids,
        "product_ids": request.product_ids,
        "start_date": request.start_date,
        "end_date": request.end_date,
        "start_time": request.start_time,
        "end_time": request.end_time,
        "shift_id": request.shift_id,
        "interval": request.interval,
        "curve_type": request.curve_type,
    })

    # Execute the single-query pipeline
    service = DashboardDataService(session)
    result = await service.get_dashboard_data(params, request.widget_ids)

    return DashboardDataResponse(**result)


@router.get("/data")
async def get_dashboard_data_get(
    widget_ids: str = Query(..., description="Comma-separated widget IDs"),
    line_id: Optional[int] = Query(None),
    line_ids: Optional[str] = Query(None),
    area_ids: Optional[str] = Query(None),
    product_ids: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    shift_id: Optional[int] = Query(None),
    interval: str = Query("hour"),
    session: AsyncSession = Depends(get_tenant_db)
):
    """
    GET version of dashboard data endpoint.
    Used by HTMX/fetch for simpler integration.
    """
    try:
        parsed_widget_ids = [int(x.strip()) for x in widget_ids.split(",")]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid widget_ids format")

    params = FilterParams.from_dict({
        "line_id": line_id,
        "line_ids": line_ids,
        "area_ids": area_ids,
        "product_ids": product_ids,
        "start_date": start_date,
        "end_date": end_date,
        "start_time": start_time,
        "end_time": end_time,
        "shift_id": shift_id,
        "interval": interval
    })

    service = DashboardDataService(session)
    result = await service.get_dashboard_data(params, parsed_widget_ids)

    return result
