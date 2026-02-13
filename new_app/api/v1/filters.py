"""
Filter API endpoints — Resolves filters dynamically via FilterEngine.

Routes:
  GET  /filters           → all active filters with resolved options
  GET  /filters/areas     → areas from cache (cascade, independent of filter_status)
  GET  /filters/{name}    → single filter by class_name
  POST /filters/validate  → validate user input dict
  GET  /filters/{name}/options?line_id=X  → cascade-aware options reload
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from new_app.core.cache import metadata_cache
from new_app.services.filters.engine import filter_engine

router = APIRouter(prefix="/filters", tags=["filters"])


@router.get("/")
async def list_filters(
    filter_ids: Optional[str] = Query(
        None,
        description="Comma-separated filter IDs to whitelist (from layout_config). "
                    "Omit to return all active filters.",
    ),
):
    """
    Return active filters with resolved options (JSON-ready).

    When ``filter_ids`` is provided (e.g. ``?filter_ids=1,2,5``),
    only those filters are returned — driven by ``layout_config``.
    """
    if not metadata_cache.is_loaded:
        raise HTTPException(status_code=503, detail="Cache not loaded — log in first")

    ids_list: Optional[List[int]] = None
    if filter_ids:
        try:
            ids_list = [int(x.strip()) for x in filter_ids.split(",") if x.strip()]
        except ValueError:
            raise HTTPException(status_code=400, detail="filter_ids must be comma-separated integers")

    return filter_engine.resolve_all(filter_ids=ids_list)


@router.get("/areas")
async def get_areas(
    line_id: Optional[int] = Query(None, description="Filter areas by line_id"),
):
    """
    Return areas from cache, optionally filtered by line_id.

    This is a direct cache lookup — AreaFilter doesn't need to be
    active (filter_status=1) for this to work.
    """
    if not metadata_cache.is_loaded:
        raise HTTPException(status_code=503, detail="Cache not loaded")
    areas = metadata_cache.get_areas()
    if line_id is not None:
        areas = {k: v for k, v in areas.items() if v["line_id"] == line_id}
    return [
        {"value": aid, "label": d["area_name"],
         "extra": {"area_type": d["area_type"], "line_id": d["line_id"]}}
        for aid, d in areas.items()
    ]


@router.get("/{class_name}")
async def get_filter(class_name: str):
    """Return a single filter by class_name."""
    if not metadata_cache.is_loaded:
        raise HTTPException(status_code=503, detail="Cache not loaded")
    result = filter_engine.resolve_one(class_name)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Filter '{class_name}' not found")
    return result


@router.get("/{class_name}/options")
async def get_filter_options(
    class_name: str,
    line_id: Optional[int] = Query(None, description="Parent line_id for cascade"),
):
    """
    Reload options for a filter — used for cascade dependencies.

    E.g. when the user selects a production line, the AreaFilter
    options are reloaded filtered by that ``line_id``.
    """
    if not metadata_cache.is_loaded:
        raise HTTPException(status_code=503, detail="Cache not loaded")

    flt = filter_engine.get_by_name(class_name)
    if flt is None:
        raise HTTPException(status_code=404, detail=f"Filter '{class_name}' not found")

    parent_values: Dict[str, Any] = {}
    if line_id is not None:
        parent_values["line_id"] = line_id

    options = flt.get_options(parent_values or None)
    return [o.to_dict() for o in options]


@router.post("/validate")
async def validate_filters(params: Dict[str, Any]):
    """
    Validate a complete set of user-chosen filter values.

    Body example::

        {
            "daterange": {"start_date":"2026-02-01","end_date":"2026-02-13"},
            "line_id": 1,
            "shift_id": null,
            "product_ids": [1,3],
            "interval": "hour"
        }
    """
    if not metadata_cache.is_loaded:
        raise HTTPException(status_code=503, detail="Cache not loaded")
    return filter_engine.validate_input(params)
