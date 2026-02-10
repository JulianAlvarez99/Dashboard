"""
Pie Chart Processor — distribution by product.

SRP: This module is solely responsible for building the pie-chart
     API response (detections grouped by product).
"""

from __future__ import annotations

from typing import Dict, Any, TYPE_CHECKING

from app.services.processors.helpers import empty_widget

if TYPE_CHECKING:
    from app.services.dashboard_data_service import DashboardData
    from app.services.widgets.aggregators import DataAggregator


def process_pie_chart(
    widget_id: int,
    name: str,
    wtype: str,
    data: "DashboardData",
    aggregator: "DataAggregator",
) -> Dict[str, Any]:
    """Distribution by product as a pie chart."""
    df = data.detections
    if df.empty or "product_name" not in df.columns:
        return empty_widget(widget_id, name, wtype)

    grouped = (
        df.groupby(["product_name", "product_color"])
        .size()
        .reset_index(name="count")
    )

    return {
        "widget_id": widget_id,
        "widget_name": name,
        "widget_type": wtype,
        "data": {
            "labels": grouped["product_name"].tolist(),
            "datasets": [
                {
                    "data": grouped["count"].tolist(),
                    "backgroundColor": grouped["product_color"].tolist(),
                }
            ],
        },
        "metadata": {"widget_category": "chart", "total_points": len(grouped)},
    }
