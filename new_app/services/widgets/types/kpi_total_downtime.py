"""KPI: Total Downtime — count and total duration of downtime events."""

from new_app.services.widgets.base import BaseWidget, WidgetResult


class KpiTotalDowntime(BaseWidget):

    def process(self) -> WidgetResult:
        dt = self.downtime_df
        count = 0
        total_minutes = 0.0

        if not dt.empty:
            count = len(dt)
            if "duration" in dt.columns:
                total_minutes = round(dt["duration"].sum() / 60.0, 1)

        return self._result(
            "kpi",
            {
                "value": count,
                "unit": "paradas",
                "total_minutes": total_minutes,
                "trend": None,
            },
            category="kpi",
        )
