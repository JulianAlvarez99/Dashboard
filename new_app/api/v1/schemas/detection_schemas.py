"""
Detection endpoint schemas — request/response Pydantic models.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DetectionQueryRequest(BaseModel):
    """Body for POST /detections/query."""
    line_ids: Optional[List[int]] = Field(
        None, description="Explicit line IDs. If null, uses line_id param.",
    )
    line_id: Optional[Any] = Field(
        None, description="Single line ID, 'all', or 'group_X'.",
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
    """Response for POST /detections/count."""
    total: int
    per_line: Dict[int, int]
