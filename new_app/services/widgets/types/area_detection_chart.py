"""Chart: Detection distribution by area — bar chart."""

from __future__ import annotations

from new_app.services.widgets.base import BaseWidget, WidgetResult
from new_app.services.widgets.helpers import FALLBACK_PALETTE


class AreaDetectionChart(BaseWidget):
    required_columns = ["area_name", "area_type"]
    default_config   = {}

    # ── Render ──────────────────────────────────────────────────
    render           = "chart"
    chart_type       = "bar_chart"
    chart_height     = "280px"

    # ── Layout ──────────────────────────────────────────────────
    tab          = "produccion"
    col_span     = 2
    row_span     = 2
    order        = 11
    downtime_only = False

    # ── JS ──────────────────────────────────────────────────────
    js_inline = """
WidgetChartBuilders['AreaDetectionChart'] = {
    zoomable: true,
    toggleable: false,
    buildConfig: function(data, options) {
        var resetBtn = options.resetBtn;
        var multi = (data.datasets || []).length > 1;
        var gridColor = ChartConfigBuilder._cssVar('--chart-grid', 'rgba(148,163,184,0.08)');
        var tickColor = ChartConfigBuilder._cssVar('--chart-tick', '#94a3b8');
        return {
            type: 'bar',
            data: {
                labels: data.labels || [],
                datasets: (data.datasets || []).map(function(ds) {
                    return {
                        label: ds.label || '',
                        data: ds.data || [],
                        backgroundColor: ds.backgroundColor || '#22c55e',
                        borderRadius: 4,
                        borderSkipped: false
                    };
                })
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: multi, position: 'top', labels: { color: tickColor, usePointStyle: true, pointStyle: 'rect', padding: 16, font: { size: 11 } } },
                    tooltip: ChartConfigBuilder._tooltipDefaults(),
                    zoom: multi ? ChartConfigBuilder._zoomOptions(resetBtn) : false
                },
                scales: {
                    x: { grid: { display: false }, ticks: { color: tickColor, font: { size: 10 }, maxTicksLimit: 14 } },
                    y: { grid: { color: gridColor }, ticks: { color: tickColor, font: { size: 10 } }, beginAtZero: true }
                }
            }
        };
    }
};
"""

    def process(self) -> WidgetResult:
        df = self.df
        if df.empty or "area_name" not in df.columns:
            return self._empty("chart")

        series = df.groupby("area_name").size().sort_values(ascending=False)

        return self._result(
            "chart",
            {
                "labels": series.index.tolist(),
                "datasets": [
                    {
                        "label": "Detecciones por Área",
                        "data": series.values.tolist(),
                        "backgroundColor": FALLBACK_PALETTE[: len(series)],
                    }
                ],
            },
            category="chart",
            total_points=len(series),
        )
