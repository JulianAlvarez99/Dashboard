"""KPI: Performance — delegates to OEE calculator, extracts performance."""

from new_app.services.widgets.base import BaseWidget, WidgetResult
from new_app.services.widgets.types.kpi_oee import _compute_oee


class KpiPerformance(BaseWidget):

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
