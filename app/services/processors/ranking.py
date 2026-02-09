"""
Ranking & Summary Processors — product_ranking, line_status, metrics_summary.

Each processor receives (widget_id, name, wtype, data[, aggregator])
and returns a Dict[str, Any] ready for the API response.
"""

from __future__ import annotations

from typing import Dict, Any, List, TYPE_CHECKING

import pandas as pd

from app.core.cache import metadata_cache
from app.services.processors.helpers import (
    empty_widget,
    calculate_scheduled_minutes,
    get_lines_with_input_output,
)

if TYPE_CHECKING:
    from app.services.dashboard_data_service import DashboardData
    from app.services.widgets.aggregators import DataAggregator


# ─── Product Ranking ─────────────────────────────────────────────────

def process_product_ranking(
    widget_id: int,
    name: str,
    wtype: str,
    data: "DashboardData",
    aggregator: "DataAggregator",
) -> Dict[str, Any]:
    """
    Top products ranked by production count.

    Returns a table-like structure with product name, count, weight,
    and percentage of total production.
    """
    df = data.detections
    if df.empty or "product_name" not in df.columns:
        return empty_widget(widget_id, name, wtype)

    # Consider only output area for production count
    if "area_type" in df.columns:
        output_df = df[df["area_type"] == "output"]
    else:
        output_df = df

    if output_df.empty:
        return empty_widget(widget_id, name, wtype)

    total = len(output_df)

    # Group by product
    grouped = (
        output_df.groupby(["product_name", "product_code", "product_color"])
        .agg(
            count=("product_name", "size"),
            total_weight=("product_weight", "sum"),
        )
        .reset_index()
        .sort_values("count", ascending=False)
    )

    rows = []
    for _, row in grouped.iterrows():
        pct = round((row["count"] / total) * 100, 1) if total > 0 else 0
        rows.append({
            "product_name": row["product_name"],
            "product_code": row["product_code"],
            "product_color": row["product_color"],
            "count": int(row["count"]),
            "total_weight": round(float(row["total_weight"]), 2),
            "percentage": pct,
        })

    columns = [
        {"key": "product_name", "label": "Producto"},
        {"key": "count", "label": "Cantidad"},
        {"key": "total_weight", "label": "Peso (kg)"},
        {"key": "percentage", "label": "% del Total"},
    ]

    return {
        "widget_id": widget_id,
        "widget_name": name,
        "widget_type": wtype,
        "data": {
            "columns": columns,
            "rows": rows,
            "total_production": total,
        },
        "metadata": {
            "widget_category": "table",
            "total_rows": len(rows),
        },
    }


# ─── Line Status ─────────────────────────────────────────────────────

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
            last_dt_str = "—"
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


# ─── Metrics Summary ─────────────────────────────────────────────────

def process_metrics_summary(
    widget_id: int,
    name: str,
    wtype: str,
    data: "DashboardData",
    aggregator: "DataAggregator",
) -> Dict[str, Any]:
    """
    Aggregated summary of key metrics across all queried lines:
    total detections, output, weight, avg rate/hour, time span, etc.
    """
    df = data.detections
    if df.empty:
        return empty_widget(widget_id, name, wtype)

    total_detections = len(df)

    # Output count
    output_count = total_detections
    if "area_type" in df.columns:
        output_count = len(df[df["area_type"] == "output"])

    # Weight
    total_weight = 0.0
    if "product_weight" in df.columns:
        if "area_type" in df.columns:
            total_weight = float(df[df["area_type"] == "output"]["product_weight"].sum())
        else:
            total_weight = float(df["product_weight"].sum())

    # Time range
    df["detected_at"] = pd.to_datetime(df["detected_at"])
    first_detection = df["detected_at"].min()
    last_detection = df["detected_at"].max()
    hours_span = (last_detection - first_detection).total_seconds() / 3600.0

    # Average rate per hour
    avg_per_hour = round(output_count / hours_span, 1) if hours_span > 0 else 0

    # Unique products
    unique_products = df["product_name"].nunique() if "product_name" in df.columns else 0

    # Lines queried
    lines_count = len(data.lines_queried)

    # Downtime info (only if available — single line)
    downtime_count = 0
    downtime_minutes = 0.0
    if not data.downtime.empty:
        downtime_count = len(data.downtime)
        if "duration" in data.downtime.columns:
            downtime_minutes = round(data.downtime["duration"].sum() / 60.0, 1)

    metrics = {
        "total_detections": total_detections,
        "output_count": output_count,
        "total_weight": round(total_weight, 2),
        "avg_per_hour": avg_per_hour,
        "hours_span": round(hours_span, 1),
        "unique_products": unique_products,
        "lines_count": lines_count,
        "downtime_count": downtime_count,
        "downtime_minutes": downtime_minutes,
        "first_detection": first_detection.strftime("%Y-%m-%d %H:%M"),
        "last_detection": last_detection.strftime("%Y-%m-%d %H:%M"),
    }

    return {
        "widget_id": widget_id,
        "widget_name": name,
        "widget_type": wtype,
        "data": metrics,
        "metadata": {
            "widget_category": "summary",
        },
    }
