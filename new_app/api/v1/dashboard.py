"""
Dashboard API Endpoints — Master orchestration pipeline (Etapa 6).

Core endpoint: POST /api/v1/dashboard/data
  1. Receives all filter parameters from the frontend.
  2. Delegates to DashboardOrchestrator which coordinates:
       FilterEngine → DetectionService → DowntimeService → WidgetEngine
  3. Returns a single JSON response with all widget data.

Secondary endpoints:
  GET  /api/v1/dashboard/data       → HTMX-friendly GET version
  POST /api/v1/dashboard/preview    → Preview with explicit widget list
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from new_app.core.cache import metadata_cache
from new_app.core.database import db_manager
from new_app.api.v1.dependencies import TenantContext, require_tenant
from new_app.services.orchestrator import dashboard_orchestrator

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# ── Pydantic request/response models ────────────────────────────

class DashboardDataRequest(BaseModel):
    """
    Request body for POST /dashboard/data.

    All filter params are optional — the orchestrator applies defaults
    via FilterEngine where needed.
    """
    # Layout control
    widget_ids: Optional[List[int]] = Field(
        None,
        description=(
            "Explicit widget IDs to render. "
            "If null, uses the layout_config for the user's role."
        ),
    )

    # Filter params (match FilterEngine param_names)
    line_id: Optional[Any] = Field(
        None, description="Single line: int, 'all', or 'group_X'.",
    )
    line_ids: Optional[str] = Field(
        None, description="Comma-separated line IDs.",
    )
    daterange: Optional[Dict[str, str]] = Field(
        None,
        description=(
            "Date range: {start_date, end_date, start_time?, end_time?}"
        ),
    )
    shift_id: Optional[int] = None
    area_ids: Optional[List[int]] = None
    product_ids: Optional[List[int]] = None
    interval: Optional[str] = Field("hour", description="Grouping interval.")
    curve_type: Optional[str] = Field("smooth", description="Chart curve type.")
    downtime_threshold: Optional[int] = Field(
        None, description="Override downtime gap threshold (seconds).",
    )
    show_downtime: Optional[bool] = Field(
        False, description="Include downtime overlay on charts.",
    )

    # Auth context (sent by Flask frontend)
    tenant_id: Optional[int] = Field(
        None, description="Tenant ID. Falls back to cached tenant.",
    )
    role: Optional[str] = Field(
        None, description="User role. Defaults to 'ADMIN'.",
    )


class DashboardMetadataResponse(BaseModel):
    """Metadata portion of the dashboard response."""
    total_detections: int = 0
    total_downtime_events: int = 0
    lines_queried: List[int] = []
    is_multi_line: bool = False
    widget_count: int = 0
    period: Dict[str, str] = {}
    interval: str = "hour"
    elapsed_seconds: float = 0
    timestamp: str = ""
    error: Optional[str] = None


class DashboardDataResponse(BaseModel):
    """Complete dashboard response."""
    widgets: Dict[str, Any]
    metadata: DashboardMetadataResponse


# ── Helpers ──────────────────────────────────────────────────────

def _extract_user_params(req: DashboardDataRequest) -> Dict[str, Any]:
    """
    Extract filter params from request body into a flat dict
    matching FilterEngine's expected ``user_params`` shape.
    """
    params: Dict[str, Any] = {}

    if req.daterange is not None:
        params["daterange"] = req.daterange
    if req.line_id is not None:
        params["line_id"] = req.line_id
    if req.line_ids is not None:
        params["line_ids"] = req.line_ids
    if req.shift_id is not None:
        params["shift_id"] = req.shift_id
    if req.area_ids is not None:
        params["area_ids"] = req.area_ids
    if req.product_ids is not None:
        params["product_ids"] = req.product_ids
    if req.interval is not None:
        params["interval"] = req.interval
    if req.curve_type is not None:
        params["curve_type"] = req.curve_type
    if req.downtime_threshold is not None:
        params["downtime_threshold"] = req.downtime_threshold
    if req.show_downtime is not None:
        params["show_downtime"] = req.show_downtime

    return params


def _resolve_tenant_id(req_tenant_id: Optional[int]) -> int:
    """Resolve tenant_id from request or cache."""
    if req_tenant_id is not None:
        return req_tenant_id
    # Attempt to infer from cache — look up in global metadata
    db_name = metadata_cache.current_tenant
    if db_name:
        # Tenant ID is typically embedded in the session, but for now
        # we use a placeholder. The real tenant_id comes from the
        # Flask session → API request.
        return 1  # fallback
    raise HTTPException(status_code=400, detail="tenant_id is required")


# ── Endpoints ────────────────────────────────────────────────────

@router.post("/data", response_model=DashboardDataResponse)
async def get_dashboard_data(
    request: DashboardDataRequest,
    ctx: TenantContext = Depends(require_tenant),
):
    """
    Master dashboard endpoint — the "Apply Filters" button hits this.

    Pipeline:
      1. Validate filters via FilterEngine.
      2. Fetch enriched detections + downtime.
      3. Resolve layout → which widgets to render.
      4. Execute all widgets via WidgetEngine.
      5. Return unified JSON response.
    """
    tenant_id = _resolve_tenant_id(request.tenant_id)
    role = request.role or "ADMIN"
    user_params = _extract_user_params(request)

    async with db_manager.get_tenant_session_by_name(ctx.db_name) as session:
        result = await dashboard_orchestrator.execute(
            session=session,
            user_params=user_params,
            tenant_id=tenant_id,
            role=role,
            widget_ids=request.widget_ids,
        )

    return result


@router.get("/data")
async def get_dashboard_data_get(
    ctx: TenantContext = Depends(require_tenant),
    widget_ids: Optional[str] = Query(
        None, description="Comma-separated widget IDs",
    ),
    line_id: Optional[str] = Query(None),
    line_ids: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    shift_id: Optional[int] = Query(None),
    area_ids: Optional[str] = Query(None),
    product_ids: Optional[str] = Query(None),
    interval: str = Query("hour"),
    tenant_id: Optional[int] = Query(None),
    role: Optional[str] = Query(None),
):
    """
    GET version of dashboard data — HTMX/fetch friendly.

    Accepts query parameters instead of a JSON body.
    """
    # Build user_params dict
    user_params: Dict[str, Any] = {"interval": interval}

    if line_id is not None:
        user_params["line_id"] = line_id
    if line_ids is not None:
        user_params["line_ids"] = line_ids
    if shift_id is not None:
        user_params["shift_id"] = shift_id

    # Build daterange dict
    if start_date or end_date:
        daterange: Dict[str, str] = {}
        if start_date:
            daterange["start_date"] = start_date
        if end_date:
            daterange["end_date"] = end_date
        if start_time:
            daterange["start_time"] = start_time
        if end_time:
            daterange["end_time"] = end_time
        user_params["daterange"] = daterange

    # Parse comma-separated IDs
    if area_ids:
        user_params["area_ids"] = [int(x.strip()) for x in area_ids.split(",")]
    if product_ids:
        user_params["product_ids"] = [
            int(x.strip()) for x in product_ids.split(",")
        ]

    # Parse widget_ids
    parsed_widget_ids = None
    if widget_ids:
        try:
            parsed_widget_ids = [int(x.strip()) for x in widget_ids.split(",")]
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid widget_ids format",
            )

    tid = _resolve_tenant_id(tenant_id)
    user_role = role or "ADMIN"

    async with db_manager.get_tenant_session_by_name(ctx.db_name) as session:
        result = await dashboard_orchestrator.execute(
            session=session,
            user_params=user_params,
            tenant_id=tid,
            role=user_role,
            widget_ids=parsed_widget_ids,
        )

    return result


@router.post("/preview")
async def preview_widgets(
    request: DashboardDataRequest,
    ctx: TenantContext = Depends(require_tenant),
):
    """
    Preview specific widgets — for testing or widget configuration.

    Requires ``widget_ids`` in the request body.
    Skips layout resolution and uses the provided widget list directly.
    """
    if not request.widget_ids:
        raise HTTPException(
            status_code=400,
            detail="widget_ids is required for preview mode",
        )

    user_params = _extract_user_params(request)

    # Use execute_quick for faster path (no layout, no validation)
    # First build cleaned directly from user_params
    from new_app.services.filters.engine import filter_engine

    validation = filter_engine.validate_input(user_params)
    cleaned = validation["cleaned"]

    # Resolve widget_ids to class names
    catalog = metadata_cache.get_widget_catalog()
    widget_names = []
    for wid in request.widget_ids:
        info = catalog.get(wid)
        if info:
            widget_names.append(info["widget_name"])

    if not widget_names:
        raise HTTPException(
            status_code=400,
            detail="None of the specified widget_ids exist in the catalog",
        )

    async with db_manager.get_tenant_session_by_name(ctx.db_name) as session:
        result = await dashboard_orchestrator.execute_quick(
            session=session,
            cleaned=cleaned,
            widget_names=widget_names,
        )

    return result
