"""
Chart: Scatter — downtime duration vs hour-of-day.

Each downtime event becomes a point:
  X = hour of day (decimal), Y = duration in minutes.
  Colored by source (orange = DB/incident, red = gap-calculated).
"""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from new_app.core.cache import metadata_cache
from new_app.services.widgets.base import BaseWidget, WidgetResult


class ScatterChart(BaseWidget):

    def process(self) -> WidgetResult:
        dt_df = self.downtime_df
        if dt_df.empty:
            return self._empty("chart")

        incidents = metadata_cache.get_incidents()

        ds_incident: List[Dict[str, Any]] = []
        ds_gap: List[Dict[str, Any]] = []

        for _, evt in dt_df.iterrows():
            st = pd.to_datetime(evt.get("start_time"))
            if pd.isna(st):
                continue

            x = round(st.hour + st.minute / 60.0, 2)
            y = round(evt.get("duration", 0) / 60.0, 1)

            reason_code = evt.get("reason_code")
            has_incident = pd.notna(reason_code) and bool(reason_code)
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
            return self._empty("chart")

        return self._result(
            "chart",
            {"datasets": datasets},
            category="chart",
            total_points=len(ds_incident) + len(ds_gap),
        )
