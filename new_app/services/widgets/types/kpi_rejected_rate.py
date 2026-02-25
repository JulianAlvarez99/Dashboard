"""
KpiRejectedRate — Percentage of rejected detections over total.

Render type : kpi
Required    : area_type column (to distinguish reject vs output)
Config keys : decimal_places (default 1)
"""

from new_app.services.widgets.base import BaseWidget, WidgetResult


class KpiRejectedRate(BaseWidget):
    required_columns = ["area_type"]
    default_config   = {"decimal_places": 1}
    render           = "kpi"

    def process(self) -> WidgetResult:
        df = self.df  # uses BaseWidget.df shorthand → self.ctx.data as DataFrame

        if df.empty or "area_type" not in df.columns:
            return self._result("kpi", {"value": 0.0, "unit": "%", "trend": None})

        total    = len(df)
        rejected = len(df[df["area_type"] == "reject"])
        decimals = int(self.ctx.config.get("decimal_places", 1))
        rate     = round((rejected / total * 100) if total > 0 else 0.0, decimals)

        return self._result(
            "kpi",
            {"value": rate, "unit": "%", "trend": None},
            category="kpi",
        )
