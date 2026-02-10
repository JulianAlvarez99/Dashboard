"""
Bar Chart Processor — distribution by area.

SRP: This module is solely responsible for building the bar-chart
     API response (detections grouped by area).
"""

from __future__ import annotations

from typing import Dict, Any, TYPE_CHECKING

from app.services.processors.helpers import empty_widget
from app.services.processors.charts.common import BAR_PALETTE

if TYPE_CHECKING:
    from app.services.dashboard_data_service import DashboardData
    from app.services.widgets.aggregators import DataAggregator


def process_bar_chart(
    widget_id: int,
    name: str,
    wtype: str,
    data: "DashboardData",
    aggregator: "DataAggregator",
) -> Dict[str, Any]:
    """Distribution by area as a bar chart."""
    df = data.detections
    if df.empty or "area_name" not in df.columns:
        return empty_widget(widget_id, name, wtype)

    series = aggregator.aggregate_by_column(df, "area_name", ascending=False)

    return {
        "widget_id": widget_id,
        "widget_name": name,
        "widget_type": wtype,
        "data": {
            "labels": series.index.tolist(),
            "datasets": [
                {
                    "label": "Detecciones por Área",
                    "data": series.values.tolist(),
                    "backgroundColor": BAR_PALETTE[: len(series)],
                }
            ],
        },
        "metadata": {"widget_category": "chart", "total_points": len(series)},
    }
