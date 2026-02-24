"""KPI: Quality — delegates to OEE calculator, extracts quality."""

from new_app.services.widgets.base import BaseWidget, WidgetResult
from new_app.services.widgets.types.kpi_oee import _compute_oee


class KpiQuality(BaseWidget):
    required_columns = ["area_type", "line_id"]
    default_config   = {}
    render           = "kpi"

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
