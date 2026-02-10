"""
Line Status Processor — real-time status of each production line.

SRP: This module is solely responsible for building the line-status
     widget API response.
"""

from __future__ import annotations

from typing import Dict, Any, TYPE_CHECKING

import pandas as pd

from app.core.cache import metadata_cache
from app.services.processors.helpers import empty_widget

if TYPE_CHECKING:
    from app.services.dashboard_data_service import DashboardData
    from app.services.widgets.aggregators import DataAggregator


def process_line_status(
    widget_id: int,
    name: str,
    wtype: str,
    data: "DashboardData",
    aggregator: "DataAggregator",
) -> Dict[str, Any]:
    """
    Status of each production line: detection count, last detection time,
    and whether the line appears to be active (detection within last 10 min).
    """
    df = data.detections
    if df.empty:
        return empty_widget(widget_id, name, wtype)

    if "line_name" not in df.columns:
        return empty_widget(widget_id, name, wtype)

    df["detected_at"] = pd.to_datetime(df["detected_at"])
    now = pd.Timestamp.now()

    lines_info = []
    for line_id in data.lines_queried:
        line_meta = metadata_cache.get_production_line(line_id)
        if not line_meta:
            continue

        line_name = line_meta["line_name"]
        line_df = df[df["line_id"] == line_id] if "line_id" in df.columns else df

        count = len(line_df)
        if count > 0:
            last_detection = line_df["detected_at"].max()
            minutes_since = (now - last_detection).total_seconds() / 60.0
            status = "active" if minutes_since < 10 else "idle"
            last_dt_str = last_detection.strftime("%Y-%m-%d %H:%M")
        else:
            status = "no_data"
            last_dt_str = "\u2014"
            minutes_since = None

        # Output count (if area_type available)
        output_count = count
        if "area_type" in line_df.columns:
            output_count = len(line_df[line_df["area_type"] == "output"])

        lines_info.append({
            "line_id": line_id,
            "line_name": line_name,
            "line_code": line_meta.get("line_code", ""),
            "status": status,
            "detection_count": count,
            "output_count": output_count,
            "last_detection": last_dt_str,
            "minutes_since_last": round(minutes_since, 1) if minutes_since is not None else None,
        })

    return {
        "widget_id": widget_id,
        "widget_name": name,
        "widget_type": wtype,
        "data": {
            "lines": lines_info,
            "total_lines": len(lines_info),
        },
        "metadata": {
            "widget_category": "status",
            "total_lines": len(lines_info),
        },
    }
