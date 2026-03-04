"""KPI: Quality — delegates to OEE calculator, extracts quality."""

from new_app.services.widgets.base import BaseWidget, WidgetResult
from new_app.services.widgets.types.kpi_oee import _compute_oee


class KpiQuality(BaseWidget):
    required_columns = ["area_type", "line_id"]
    default_config   = {}

    # ── Render ──────────────────────────────────────────────
    render       = "kpi"
    chart_type   = ""
    chart_height = "250px"

    # ── Layout ──────────────────────────────────────────────
    tab          = "oee"
    col_span     = 1
    row_span     = 1
    order        = 3
    downtime_only = False

    # ── JS ──────────────────────────────────────────────────
    js_inline = None

    def process(self) -> WidgetResult:
        calc = _compute_oee(self.ctx)
        return self._result(
            "kpi",
            {
                "value": calc["quality"],
                "unit": "%",
                "trend": None,
            },
            category="kpi",
        )
