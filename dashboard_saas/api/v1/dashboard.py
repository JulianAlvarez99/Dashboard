"""
Dashboard API — Filter options, apply filters, raw data.

Phase 3: Focus on filter options and SQL clause generation.
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from dashboard_saas.core.cache import metadata_cache
from dashboard_saas.core.database import db_manager
from dashboard_saas.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


# ── Pydantic models for request/response ─────────────────────────

class ApplyFiltersRequest(BaseModel):
    """Request body for applying filters."""
    filters: Dict[str, Any]  # { param_name: value, ... }


class ApplyFiltersResponse(BaseModel):
    """Response with the SQL query and raw data."""
    status: str
    tables_queried: List[str]
    query: str
    params: Dict[str, Any]
    row_count: int
    data: List[Dict]


# ── Filter options ───────────────────────────────────────────────

@router.get("/filters")
async def get_filters():
    """
    Return all active filters, serialized for the frontend.
    """
    from dashboard_saas.services.filters.engine import filter_engine
    return {"filters": filter_engine.get_all_serialized()}


@router.get("/widgets")
async def get_widgets():
    """Return all discovered widgets (Phase 3: metadata only)."""
    from dashboard_saas.services.widgets.engine import widget_engine
    return {"widgets": widget_engine.get_all_serialized()}


# ── Apply filters → build query → execute → return raw data ─────

@router.post("/apply-filters", response_model=ApplyFiltersResponse)
async def apply_filters(request: ApplyFiltersRequest):
    """
    Apply filters and return raw detection data.

    Flow:
    1. Collect SQL clauses from each filter via FilterEngine.
    2. Resolve the detection table name(s) from the selected line.
    3. Build the query via QueryBuilder.
    4. Execute against the tenant DB.
    5. Return raw rows (no processing — that's Phase 4+).
    """
    from sqlalchemy import text
    from dashboard_saas.services.filters.engine import filter_engine
    from dashboard_saas.services.data.query_builder import query_builder

    filter_values = request.filters

    # Validate: need at least line_id
    if "line_id" not in filter_values:
        raise HTTPException(status_code=400, detail="line_id is required")

    # 1. Collect SQL clauses from the globally loaded filter engine
    clauses, params = filter_engine.collect_sql_clauses(filter_values)

    # 2. Resolve table names from the line_id value
    line_filter = filter_engine.get("line_id")
    if not line_filter:
        raise HTTPException(status_code=500, detail="ProductionLineFilter not loaded")

    # Get options as dicts for the query builder
    line_options = [
        {"value": o.value, "label": o.label, "extra": o.extra}
        for o in line_filter.get_options()
    ]
    table_names = query_builder.resolve_table_names(
        filter_values["line_id"], line_options
    )

    if not table_names:
        raise HTTPException(
            status_code=400,
            detail=f"Could not resolve table for line_id={filter_values['line_id']}"
        )

    # 3. Build and execute queries (one per table)
    all_rows: List[Dict] = []
    db_name = metadata_cache.current_tenant
    if not db_name:
        raise HTTPException(status_code=500, detail="No tenant loaded in cache")

    # Remove line_id clause for multi-table queries (already resolved via table name)
    # Keep it for single table queries (in case table has multi-line data)
    query_clauses = clauses
    query_params = params

    for table_name in table_names:
        sql, p = query_builder.build_detection_query(table_name, query_clauses, query_params)

        try:
            with db_manager.get_tenant_session(db_name) as session:
                result = session.execute(text(sql), p)
                rows = [dict(row) for row in result.mappings().all()]
                all_rows.extend(rows)
                logger.info("Queried %s: %d rows", table_name, len(rows))
        except Exception as e:
            logger.error("Query failed for %s: %s", table_name, e, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

    # Build display query (for debugging/transparency)
    display_sql, _ = query_builder.build_detection_query(
        table_names[0], query_clauses, query_params
    )

    return ApplyFiltersResponse(
        status="ok",
        tables_queried=table_names,
        query=display_sql,
        params={k: str(v) for k, v in query_params.items()},
        row_count=len(all_rows),
        data=all_rows,
    )
