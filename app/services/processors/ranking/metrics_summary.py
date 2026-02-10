"""
Metrics Summary Processor — aggregated KPI summary across queried lines.

SRP: This module is solely responsible for building the metrics-summary
     widget API response.
"""

from __future__ import annotations

from typing import Dict, Any, TYPE_CHECKING

import pandas as pd

from app.services.processors.helpers import empty_widget

if TYPE_CHECKING:
    from app.services.dashboard_data_service import DashboardData
    from app.services.widgets.aggregators import DataAggregator


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

    # Downtime info (only if available)
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
