"""KPI: Availability — delegates to OEE calculator, extracts availability."""

from new_app.services.widgets.base import BaseWidget, WidgetResult
from new_app.services.widgets.types.kpi_oee import _compute_oee


class KpiAvailability(BaseWidget):

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
