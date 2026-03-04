"""KPI: Total Production — count of 'output' detections."""

from new_app.services.widgets.base import BaseWidget, WidgetResult


class KpiTotalProduction(BaseWidget):
    required_columns = ["area_type"]
    default_config   = {"unit": "unidades"}

    # ── Render ──────────────────────────────────────────────
    render       = "kpi"
    chart_type   = ""
    chart_height = "250px"

    # ── Layout ──────────────────────────────────────────────
    tab          = "produccion"
    col_span     = 1
    row_span     = 1
    order        = 7
    downtime_only = False

    # ── JS ──────────────────────────────────────────────────
    js_inline = None

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
