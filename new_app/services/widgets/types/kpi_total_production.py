"""KPI: Total Production — count of 'output' detections."""

from new_app.services.widgets.base import BaseWidget, WidgetResult


class KpiTotalProduction(BaseWidget):

    def process(self) -> WidgetResult:
        df = self.df
        if not df.empty and "area_type" in df.columns:
            value = int(len(df[df["area_type"] == "output"]))
        else:
            value = len(df)

        unit = self.ctx.config.get("unit", "unidades")

        return self._result(
            "kpi",
            {"value": value, "unit": unit, "trend": None},
            category="kpi",
        )
