"""KPI: Performance — delegates to OEE calculator, extracts performance."""

from new_app.services.widgets.base import BaseWidget, WidgetResult
from new_app.services.widgets.types.kpi_oee import _compute_oee


class KpiPerformance(BaseWidget):
    required_columns = ["area_type", "detected_at", "line_id"]
    default_config   = {}
    render           = "kpi"

    def process(self) -> WidgetResult:
        calc = _compute_oee(self.ctx)
        return self._result(
            "kpi",
            {
                "value": calc["performance"],
                "unit": "%",
                "trend": None,
            },
            category="kpi",
        )
