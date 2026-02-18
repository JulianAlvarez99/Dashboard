"""
Detection API endpoints — Fetch, count and export enriched detections.

Routes:
  POST /detections/query          → enriched detections (filters in body)
  GET  /detections/{line_id}      → paginated detections for one line
  POST /detections/count          → count per line without fetching rows
  POST /detections/summary        → counts grouped by area_type
  POST /detections/export         → CSV or XLSX download
  POST /detections/partitions/ensure/{line_id}  → admin partition management
  GET  /detections/partitions/{line_id}         → list partitions

These endpoints are used for debugging, standalone queries, and data
export.  The main dashboard pipeline (Etapa 6) will call DetectionService
directly — it doesn't go through these HTTP endpoints.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from new_app.core.database import db_manager
from new_app.api.v1.dependencies import (
    TenantContext,
    require_tenant,
    resolve_line_ids_from_cleaned,
)
from new_app.services.data.detection_service import detection_service
from new_app.services.data.enrichment import enrich_detections
from new_app.services.data.export import format_datetime_columns, to_csv, to_excel_bytes
from new_app.services.data.table_resolver import table_resolver

router = APIRouter(prefix="/detections", tags=["detections"])


# ── Pydantic models ──────────────────────────────────────────────

class DetectionQueryRequest(BaseModel):
    """Body for POST /detections/query."""
    line_ids: Optional[List[int]] = Field(
        None, description="Explicit line IDs. If null, uses line_id param."
    )
    line_id: Optional[Any] = Field(
        None, description="Single line ID, 'all', or 'group_X'."
    )
    daterange: Optional[Dict[str, str]] = Field(
        None,
        description="Date range: {start_date, end_date, start_time?, end_time?}",
    )
    shift_id: Optional[int] = None
    area_ids: Optional[List[int]] = None
    product_ids: Optional[List[int]] = None
    interval: Optional[str] = "hour"


class DetectionCountResponse(BaseModel):
    total: int
    per_line: Dict[int, int]


# ── Helpers ──────────────────────────────────────────────────────

def _build_cleaned(req: DetectionQueryRequest) -> Dict[str, Any]:
    """Build the cleaned dict matching FilterEngine output shape."""
    cleaned: Dict[str, Any] = {}
    if req.daterange:
        cleaned["daterange"] = req.daterange
    if req.shift_id is not None:
        cleaned["shift_id"] = req.shift_id
    if req.area_ids:
        cleaned["area_ids"] = req.area_ids
    if req.product_ids:
        cleaned["product_ids"] = req.product_ids
    if req.line_id is not None:
        cleaned["line_id"] = req.line_id
    if req.line_ids is not None:
        cleaned["line_ids"] = req.line_ids
    if req.interval:
        cleaned["interval"] = req.interval
    return cleaned


# ── Endpoints ────────────────────────────────────────────────────

@router.post("/query")
async def query_detections(
    req: DetectionQueryRequest,
    ctx: TenantContext = Depends(require_tenant),
):
    """
    Fetch enriched detections for the given filters.

    Returns a JSON array of records (one dict per detection row)
    with all enrichment columns.
    """
    cleaned = _build_cleaned(req)
    line_ids = resolve_line_ids_from_cleaned(cleaned)

    async with db_manager.get_tenant_session_by_name(ctx.db_name) as session:
        df = await detection_service.get_enriched_detections(
            session=session,
            line_ids=line_ids,
            cleaned=cleaned,
        )

    if df.empty:
        return {"data": [], "total": 0, "lines_queried": line_ids}

    format_datetime_columns(df)
    return {
        "data": df.to_dict(orient="records"),
        "total": len(df),
        "lines_queried": line_ids,
    }


@router.get("/{line_id}")
async def get_line_detections(
    line_id: int,
    ctx: TenantContext = Depends(require_tenant),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    start_time: Optional[str] = Query(None, description="HH:MM"),
    end_time: Optional[str] = Query(None, description="HH:MM"),
    shift_id: Optional[int] = Query(None),
    limit: int = Query(1000, ge=1, le=100_000),
):
    """
    Fetch detections for a single production line (GET convenience).
    """
    cleaned: Dict[str, Any] = {}
    if start_date or end_date:
        cleaned["daterange"] = {
            "start_date": start_date or "2020-01-01",
            "end_date": end_date or "2099-12-31",
            "start_time": start_time or "00:00",
            "end_time": end_time or "23:59",
        }
    if shift_id is not None:
        cleaned["shift_id"] = shift_id

    table_name = table_resolver.detection_table(line_id)
    if not table_name:
        raise HTTPException(
            status_code=404, detail=f"Line {line_id} not found in cache"
        )

    async with db_manager.get_tenant_session_by_name(ctx.db_name) as session:
        from new_app.services.data.detection_repository import (
            detection_repository,
        )

        raw_df = await detection_repository.fetch_detections(
            session=session,
            table_name=table_name,
            cleaned=cleaned,
            max_rows=limit,
        )

    if raw_df.empty:
        return {"data": [], "total": 0, "line_id": line_id}

    raw_df["line_id"] = line_id
    enriched = enrich_detections(raw_df)
    format_datetime_columns(enriched)

    return {
        "data": enriched.to_dict(orient="records"),
        "total": len(enriched),
        "line_id": line_id,
    }


@router.post("/count")
async def count_detections(
    req: DetectionQueryRequest,
    ctx: TenantContext = Depends(require_tenant),
):
    """
    Return detection counts per line without fetching rows.
    """
    cleaned = _build_cleaned(req)
    line_ids = resolve_line_ids_from_cleaned(cleaned)

    async with db_manager.get_tenant_session_by_name(ctx.db_name) as session:
        result = await detection_service.get_detection_count(
            session=session,
            line_ids=line_ids,
            cleaned=cleaned,
        )

    return result


@router.post("/summary")
async def detection_summary(
    req: DetectionQueryRequest,
    ctx: TenantContext = Depends(require_tenant),
):
    """
    Return detection summary with counts by area_type.
    """
    cleaned = _build_cleaned(req)
    line_ids = resolve_line_ids_from_cleaned(cleaned)

    async with db_manager.get_tenant_session_by_name(ctx.db_name) as session:
        result = await detection_service.get_detection_summary(
            session=session,
            line_ids=line_ids,
            cleaned=cleaned,
        )

    return result


@router.post("/export")
async def export_detections(
    req: DetectionQueryRequest,
    ctx: TenantContext = Depends(require_tenant),
    format: str = Query("csv", description="Export format: csv | xlsx"),
):
    """
    Export enriched detections as CSV or XLSX file.
    """
    cleaned = _build_cleaned(req)
    line_ids = resolve_line_ids_from_cleaned(cleaned)

    async with db_manager.get_tenant_session_by_name(ctx.db_name) as session:
        df = await detection_service.get_enriched_detections(
            session=session,
            line_ids=line_ids,
            cleaned=cleaned,
        )

    if df.empty:
        raise HTTPException(status_code=404, detail="No data to export")

    if format == "xlsx":
        content = to_excel_bytes(df)
        return Response(
            content=content,
            media_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            headers={
                "Content-Disposition": "attachment; filename=detecciones.xlsx"
            },
        )

    csv_content = to_csv(df)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=detecciones.csv"
        },
    )


# ── Partition management (admin only) ────────────────────────────

@router.post("/partitions/ensure/{line_id}")
async def ensure_partitions(
    line_id: int,
    ctx: TenantContext = Depends(require_tenant),
    months_ahead: int = Query(3, ge=1, le=24),
):
    """
    Ensure monthly partitions exist for a detection table.

    This is an administrative endpoint — should be called by cron
    or manually, not by the dashboard UI.
    """
    table_name = table_resolver.detection_table(line_id)
    if not table_name:
        raise HTTPException(
            status_code=404, detail=f"Line {line_id} not found"
        )

    from new_app.services.data.partition_manager import partition_manager

    async with db_manager.get_tenant_session_by_name(ctx.db_name) as session:
        created = await partition_manager.ensure_partitions(
            session=session,
            table_name=table_name,
            months_ahead=months_ahead,
        )

    return {
        "table": table_name,
        "partitions_created": created,
        "count": len(created),
    }


@router.get("/partitions/{line_id}")
async def list_partitions(
    line_id: int,
    ctx: TenantContext = Depends(require_tenant),
):
    """
    List existing partitions on a detection table.
    """
    table_name = table_resolver.detection_table(line_id)
    if not table_name:
        raise HTTPException(
            status_code=404, detail=f"Line {line_id} not found"
        )

    from new_app.services.data.partition_manager import partition_manager

    async with db_manager.get_tenant_session_by_name(ctx.db_name) as session:
        partitions = await partition_manager.get_existing_partitions(
            session=session, table_name=table_name
        )

    return {
        "table": table_name,
        "partitions": partitions,
        "count": len(partitions),
    }
