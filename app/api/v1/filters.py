"""
Filters API Endpoints
Provides filter configurations and dynamic options for the dashboard
"""

from typing import Dict, List, Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.filters.filter_resolver import FilterResolver
from app.core.cache import metadata_cache


router = APIRouter()


# === Pydantic Response Models ===

class FilterOptionResponse(BaseModel):
    """Single filter option"""
    value: Any
    label: str
    extra: Optional[Dict[str, Any]] = None


class FilterConfigResponse(BaseModel):
    """Complete filter configuration"""
    filter_id: int
    filter_name: str
    description: str
    filter_type: str
    display_order: int
    options: List[FilterOptionResponse]
    depends_on: Optional[str]
    required: bool
    default_value: Any
    ui_config: Dict[str, Any]


class ProductionLineOption(BaseModel):
    """Production line option"""
    value: Any
    label: str
    line_code: Optional[str] = None
    downtime_threshold: Optional[int] = None
    is_group: bool = False
    line_ids: Optional[List[int]] = None


class AreaOption(BaseModel):
    """Area option"""
    value: int
    label: str
    area_type: str


class ProductOption(BaseModel):
    """Product option"""
    value: int
    label: str
    product_code: str
    product_weight: float
    product_color: str


class ShiftOption(BaseModel):
    """Shift option"""
    value: int
    label: str
    start_time: str
    end_time: str
    is_overnight: bool


# === Endpoints ===

@router.get("/config/{filter_id}", response_model=FilterConfigResponse)
async def get_filter_config(
    filter_id: int,
    line_id: Optional[int] = Query(None, description="Parent line ID for cascade")
):
    """
    Get complete configuration for a specific filter.
    
    Includes options loaded from cache, respecting dependencies.
    """
    parent_values = {}
    if line_id is not None:
        parent_values["line_id"] = line_id
    
    config = FilterResolver.resolve_filter(filter_id, parent_values)
    
    if config is None:
        raise HTTPException(status_code=404, detail=f"Filter {filter_id} not found")
    
    return FilterConfigResponse(**config.to_dict())


@router.get("/configs", response_model=List[FilterConfigResponse])
async def get_filters_configs(
    filter_ids: str = Query(..., description="Comma-separated filter IDs"),
    line_id: Optional[int] = Query(None, description="Parent line ID for cascade")
):
    """
    Get configurations for multiple filters.
    
    Use this to load all enabled filters for a dashboard at once.
    """
    try:
        ids = [int(fid.strip()) for fid in filter_ids.split(",")]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filter_ids format")
    
    parent_values = {}
    if line_id is not None:
        parent_values["line_id"] = line_id
    
    configs = FilterResolver.resolve_filters(ids, parent_values)
    
    return [FilterConfigResponse(**c.to_dict()) for c in configs]


@router.get("/options/production-lines", response_model=List[ProductionLineOption])
async def get_production_line_options():
    """
    Get all production line options including line groups.
    
    Groups come from filter.additional_filter with format:
    {"alias": "Fraccionado", "line_ids": [2, 3, 4]}
    """
    options = FilterResolver.get_production_line_options_with_groups()
    return [ProductionLineOption(**opt) for opt in options]


@router.get("/options/areas", response_model=List[AreaOption])
async def get_area_options(
    line_id: Optional[int] = Query(None, description="Filter by production line")
):
    """
    Get area options, optionally filtered by production line.
    
    For cascade: when user selects a line, reload areas for that line.
    """
    if line_id is not None:
        options = FilterResolver.get_areas_for_line(line_id)
    else:
        areas = metadata_cache.get_areas()
        options = [
            {
                "value": area_id,
                "label": data["area_name"],
                "area_type": data["area_type"]
            }
            for area_id, data in areas.items()
        ]
    
    return [AreaOption(**opt) for opt in options]


@router.get("/options/products", response_model=List[ProductOption])
async def get_product_options():
    """
    Get all product options.
    
    Used to populate the product multiselect/dropdown.
    """
    options = FilterResolver.get_product_options()
    return [ProductOption(**opt) for opt in options]


@router.get("/options/shifts", response_model=List[ShiftOption])
async def get_shift_options():
    """
    Get all shift options.
    
    Used to populate the shift dropdown.
    """
    options = FilterResolver.get_shift_options()
    return [ShiftOption(**opt) for opt in options]


@router.get("/options/{filter_id}", response_model=List[FilterOptionResponse])
async def get_filter_options(
    filter_id: int,
    line_id: Optional[int] = Query(None, description="Parent line ID for cascade")
):
    """
    Get options for a specific filter by ID.
    
    This is useful for HTMX cascade updates.
    """
    parent_values = {}
    if line_id is not None:
        parent_values["line_id"] = line_id
    
    options = FilterResolver.get_filter_options(filter_id, parent_values)
    
    return [FilterOptionResponse(**opt) for opt in options]
