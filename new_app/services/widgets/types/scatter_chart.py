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
    required_columns = []
    default_config   = {}

    # ── Render ──────────────────────────────────────────────────
    render           = "chart"
    chart_type       = "scatter_chart"
    chart_height     = "300px"

    # ── Layout ──────────────────────────────────────────────────
    tab          = "produccion"
    col_span     = 2
    row_span     = 2
    order        = 13
    downtime_only = True

    # ── JS ──────────────────────────────────────────────────────
    js_inline = """
WidgetChartBuilders['ScatterChart'] = {
    zoomable: true,
    toggleable: false,
    buildConfig: function(data, options) {
        var resetBtn = options.resetBtn;
        return {
            type: 'scatter',
            data: {
                datasets: (data.datasets || []).map(function(ds) {
                    return {
                        label: ds.label || '',
                        data: ds.data || [],
                        backgroundColor: ds.backgroundColor || '#22c55e',
                        borderColor: ds.borderColor || '#22c55e',
                        pointRadius: ds.pointRadius || 6,
                        pointHoverRadius: 9
                    };
                })
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        type: 'linear', position: 'bottom',
                        title: { display: true, text: 'Hora del Día (0-24)', color: '#94a3b8' },
                        min: 0, max: 24,
                        grid: { color: 'rgba(148,163,184,0.08)' },
                        ticks: { color: '#94a3b8', stepSize: 2 }
                    },
                    y: {
                        title: { display: true, text: 'Duración (min)', color: '#94a3b8' },
                        beginAtZero: true,
                        grid: { color: 'rgba(148,163,184,0.08)' },
                        ticks: { color: '#94a3b8' }
                    }
                },
                plugins: {
                    legend: { display: true, position: 'top', labels: { color: '#94a3b8', usePointStyle: true, padding: 16, font: { size: 11 } } },
                    tooltip: Object.assign({}, ChartConfigBuilder._tooltipDefaults(), {
                        callbacks: {
                            label: function(ctx) {
                                var p = ctx.raw;
                                var h = Math.floor(p.x);
                                var m = Math.round((p.x - h) * 60);
                                var lbl = h + ':' + String(m).padStart(2, '0') + ' — ' + p.y + ' min';
                                if (p.tooltip) lbl += ' | ' + p.tooltip;
                                return lbl;
                            }
                        }
                    }),
                    zoom: ChartConfigBuilder._zoomOptions(resetBtn)
                }
            }
        };
    }
};
"""

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
