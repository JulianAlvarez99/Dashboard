"""KPI: Availability — delegates to OEE calculator, extracts availability."""

from new_app.services.widgets.base import BaseWidget, WidgetResult
from new_app.services.widgets.types.kpi_oee import _compute_oee


class KpiAvailability(BaseWidget):
    required_columns = ["area_type", "detected_at", "line_id"]
    default_config   = {}

    # ── Render ──────────────────────────────────────────────
    render       = "kpi"
    chart_type   = ""
    chart_height = "250px"

    # ── Layout ──────────────────────────────────────────────
    tab          = "oee"
    col_span     = 1
    row_span     = 1
    order        = 1
    downtime_only = False

    # ── JS ──────────────────────────────────────────────────
    js_inline = None

    def process(self) -> WidgetResult:
        calc = _compute_oee(self.ctx)
        return self._result(
            "kpi",
            {
                "value": calc["availability"],
                "unit": "%",
                "scheduled_minutes": calc["scheduled_minutes"],
                "downtime_minutes": calc["downtime_minutes"],
                "trend": None,
            },
            category="kpi",
        )
