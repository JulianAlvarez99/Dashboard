"""
Dashboard endpoint schemas — request/response Pydantic models.

DashboardDataRequest has ``extra='allow'`` so newly added filter params
are accepted transparently without code changes. The actual filter param
extraction (build_filter_dict) discovers active params from FilterEngine
at request time, making the system fully generic.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DashboardDataRequest(BaseModel):
    """
    Request body for POST /dashboard/data.

    extra='allow': accepts any additional filter params from newly added
    filter classes without requiring changes to this file.
    """

    model_config = ConfigDict(extra="allow")

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
    charts: Optional[Dict[str, str]] = Field(
        None,
        description="Base64 encoded chart images (dict mapping widget_id to base64 string).",
    )

    # Auth context — DEPRECATED: these fields are ignored.
    # tenant_id and role are always taken from the validated JWT (TenantContext).
    # Kept for backwards compatibility with external clients only.
    tenant_id: Optional[int] = Field(
        None, description="[DEPRECATED] Ignored. Tenant is resolved from JWT.",
    )
    role: Optional[str] = Field(
        None, description="[DEPRECATED] Ignored. Role is resolved from JWT.",
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
