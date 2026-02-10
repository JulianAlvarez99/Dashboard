"""
Scatter Chart Processor — downtime duration vs hour-of-day.

SRP: This module is solely responsible for building the scatter-chart
     API response (downtime events as X/Y points).
"""

from __future__ import annotations

from typing import Dict, Any, List, TYPE_CHECKING

import pandas as pd

from app.services.processors.helpers import empty_widget
from app.core.cache import metadata_cache

if TYPE_CHECKING:
    from app.services.dashboard_data_service import DashboardData
    from app.services.widgets.aggregators import DataAggregator


def process_scatter_chart(
    widget_id: int,
    name: str,
    wtype: str,
    data: "DashboardData",
    aggregator: "DataAggregator",
) -> Dict[str, Any]:
    """
    Scatter plot: each downtime event becomes a point.
    X = hour of day (decimal), Y = duration in minutes.
    Color by source (orange = DB/incident, red = gap-calculated).
    """
    dt_df = data.downtime
    if dt_df.empty:
        return empty_widget(widget_id, name, wtype)

    incidents = metadata_cache.get_incidents()

    ds_incident: List[Dict[str, Any]] = []
    ds_gap: List[Dict[str, Any]] = []

    for _, evt in dt_df.iterrows():
        st = pd.to_datetime(evt.get("start_time"))
        if pd.isna(st):
            continue
        x = round(st.hour + st.minute / 60.0, 2)
        y = round(evt.get("duration", 0) / 60.0, 1)  # seconds → minutes

        reason_code = evt.get("reason_code")
        has_incident = pd.notna(reason_code) and reason_code
        incident = incidents.get(int(reason_code)) if has_incident else None
        tooltip = incident["description"] if incident else ""

        point = {"x": x, "y": y, "tooltip": tooltip}
        if has_incident:
            ds_incident.append(point)
        else:
            ds_gap.append(point)

    datasets: List[Dict[str, Any]] = []
    if ds_incident:
        datasets.append({
            "label": "Con incidente",
            "data": ds_incident,
            "backgroundColor": "rgba(249,115,22,0.7)",
            "borderColor": "rgba(249,115,22,1)",
            "pointRadius": 6,
        })
    if ds_gap:
        datasets.append({
            "label": "Detectada (gap)",
            "data": ds_gap,
            "backgroundColor": "rgba(239,68,68,0.7)",
            "borderColor": "rgba(239,68,68,1)",
            "pointRadius": 6,
        })

    if not datasets:
        return empty_widget(widget_id, name, wtype)

    return {
        "widget_id": widget_id,
        "widget_name": name,
        "widget_type": wtype,
        "data": {
            "datasets": datasets,
        },
        "metadata": {
            "widget_category": "chart",
            "total_points": len(ds_incident) + len(ds_gap),
        },
    }
