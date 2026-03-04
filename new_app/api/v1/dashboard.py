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
from new_app.api.v1.dependencies import TenantContext, require_role, require_tenant
from new_app.services.orchestrator import dashboard_orchestrator
from new_app.utils.request_helpers import build_filter_dict

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# Schemas imported from the schemas package to keep this module thin
from new_app.api.v1.schemas import (  # noqa: E402
    DashboardDataRequest,
    DashboardDataResponse,
    DashboardMetadataResponse,
)


# ── Helpers ──────────────────────────────────────────────────────

def _extract_user_params(req: DashboardDataRequest) -> Dict[str, Any]:
    """
    Extract filter params from request body into a flat dict
    matching FilterEngine's expected ``user_params`` shape.

    Delegates to the shared ``build_filter_dict`` utility (DRY).
    """
    return build_filter_dict(req)


# ── Endpoints ────────────────────────────────────────────────────

@router.post("/data", response_model=DashboardDataResponse)
async def get_dashboard_data(
    request: DashboardDataRequest,
    ctx: TenantContext = Depends(require_role("ADMIN", "MANAGER", "OPERATOR")),
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
    # tenant_id and role come from the validated JWT — never from the body
    tenant_id = ctx.tenant_id
    role = ctx.role
    user_params = _extract_user_params(request)

    t_start = _time.perf_counter()

    result = await dashboard_orchestrator.execute(
        session=None,
        user_params=user_params,
        tenant_id=tenant_id,
        role=role,
        widget_ids=request.widget_ids,
        include_raw=request.include_raw,
        db_name=ctx.db_name,
    )

    duration_ms = int((_time.perf_counter() - t_start) * 1000)

    # ── Fire-and-forget: log the query activity ───────────────
    try:
        from new_app.services.audit.query_log_service import query_log_service  # noqa: PLC0415
        # ctx is the TenantContext built by require_tenant() from the JWT —
        # it already carries the real user_id and username decoded from the
        # Bearer token.  No need for metadata_cache.get_current_user().
        query_log_service.log_query_async(
            user_id=ctx.user_id,
            username=ctx.username,
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
    ctx: TenantContext = Depends(require_role("ADMIN", "MANAGER", "OPERATOR")),
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

    # tenant_id and role come from the validated JWT — never from query params
    tid = ctx.tenant_id
    user_role = ctx.role

    result = await dashboard_orchestrator.execute(
        session=None,
        user_params=user_params,
        tenant_id=tid,
        role=user_role,
        widget_ids=parsed_widget_ids,
        db_name=ctx.db_name,
    )

    return result


@router.post("/preview")
async def preview_widgets(
    request: DashboardDataRequest,
    ctx: TenantContext = Depends(require_role("ADMIN", "MANAGER")),
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

    result = await dashboard_orchestrator.execute_quick(
        session=None,
        cleaned=cleaned,
        widget_names=widget_names,
        db_name=ctx.db_name,
    )

    return result

from fastapi.responses import Response as FastAPIResponse

@router.post("/export/pdf")
async def export_dashboard_pdf(
    request: DashboardDataRequest,
    tenant_ctx: TenantContext = Depends(require_role("ADMIN", "MANAGER")),
):
    """Exportar el dashboard actual a PDF."""
    # Reutiliza el mismo pipeline que /dashboard/data
    result = await dashboard_orchestrator.execute(
        session=None,
        user_params=build_filter_dict(request),
        tenant_id=tenant_ctx.tenant_id,
        role=tenant_ctx.role,
        widget_ids=request.widget_ids,
        include_raw=request.include_raw,
        db_name=tenant_ctx.db_name,
    )

    from new_app.services.data.export import to_pdf_bytes
    import pandas as pd

    # Reconstruir DataFrames desde raw si están disponibles
    raw_dt = result.get("raw_downtime") or []
    downtime_df = pd.DataFrame(raw_dt) if raw_dt else None
    if downtime_df is not None and not downtime_df.empty:
        for col in ("start_time","end_time"):
            if col in downtime_df.columns:
                downtime_df[col] = pd.to_datetime(downtime_df[col], errors="coerce")

    pdf_bytes = to_pdf_bytes(
        widgets=result.get("widgets", {}),
        metadata=result.get("metadata", {}),
        downtime_df=downtime_df,
        charts=request.charts,
    )

    return FastAPIResponse(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="dashboard.pdf"'},
    )
