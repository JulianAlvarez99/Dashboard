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

import time as _time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from new_app.core.cache import metadata_cache
from new_app.core.database import db_manager
from new_app.api.v1.dependencies import TenantContext, require_tenant
from new_app.services.orchestrator import dashboard_orchestrator
from new_app.utils.request_helpers import build_filter_dict

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

    # Raw data mode (for client-side re-aggregation without re-query)
    include_raw: bool = Field(
        False,
        description=(
            "When True, includes raw_data (detections) and raw_downtime "
            "arrays in the response so the frontend can re-aggregate by "
            "shift/interval/product without a new DB query."
        ),
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

    Delegates to the shared ``build_filter_dict`` utility (DRY).
    """
    return build_filter_dict(req)


def _resolve_tenant_id(req_tenant_id: Optional[int]) -> int:
    """Resolve tenant_id from request body. Required — no fallback."""
    if req_tenant_id is not None:
        return req_tenant_id
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

    t_start = _time.perf_counter()

    async with db_manager.get_tenant_session_by_name(ctx.db_name) as session:
        result = await dashboard_orchestrator.execute(
            session=session,
            user_params=user_params,
            tenant_id=tenant_id,
            role=role,
            widget_ids=request.widget_ids,
            include_raw=request.include_raw,
        )

    duration_ms = int((_time.perf_counter() - t_start) * 1000)

    # ── Fire-and-forget: log the query activity ───────────────
    try:
        from new_app.services.audit.query_log_service import query_log_service  # noqa: PLC0415
        user = metadata_cache.get_current_user() if hasattr(metadata_cache, "get_current_user") else None
        user_id = (user or {}).get("user_id", 0)
        username = (user or {}).get("username", "unknown")
        query_log_service.log_query_async(
            user_id=user_id,
            username=username,
            filters=user_params,
            line=str(request.line_id or request.line_ids or "all"),
            interval_type=request.interval or "hour",
            duration_ms=duration_ms,
        )
    except Exception:
        pass  # query log failure must never break the response

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
