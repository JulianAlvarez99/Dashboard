"""
Request helpers — shared utilities for converting Pydantic request
models into the flat ``user_params`` / ``cleaned`` dict that
FilterEngine expects.

Centralises the mapping logic that was previously duplicated in:
  - api/v1/dashboard.py  (_extract_user_params)
  - api/v1/detections.py (_build_cleaned)
"""

from typing import Any, Dict


def build_filter_dict(req) -> Dict[str, Any]:
    """
    Extract filter params from a Pydantic request model into a flat
    dict matching FilterEngine's expected ``user_params`` shape.

    Only fields with a non-None value are included so that FilterEngine
    can correctly distinguish "not provided" from "explicitly set to None".

    Compatible with both ``DashboardDataRequest`` and
    ``DetectionQueryRequest`` (and any future request model that exposes
    the same field names).
    """
    mapping = {
        "daterange": "daterange",
        "line_id": "line_id",
        "line_ids": "line_ids",
        "shift_id": "shift_id",
        "area_ids": "area_ids",
        "product_ids": "product_ids",
        "interval": "interval",
        "curve_type": "curve_type",
        "downtime_threshold": "downtime_threshold",
        "show_downtime": "show_downtime",
    }

    params: Dict[str, Any] = {}
    for attr, key in mapping.items():
        value = getattr(req, attr, None)
        if value is not None:
            params[key] = value

    return params
