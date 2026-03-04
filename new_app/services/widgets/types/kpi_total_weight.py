"""KPI: Total Weight — sum of product_weight for output detections."""

from new_app.services.widgets.base import BaseWidget, WidgetResult


class KpiTotalWeight(BaseWidget):
    required_columns = ["area_type", "product_weight"]
    default_config   = {"unit": "kg"}

    # ── Render ──────────────────────────────────────────────
    render       = "kpi"
    chart_type   = ""
    chart_height = "250px"

    # ── Layout ──────────────────────────────────────────────
    tab          = "produccion"
    col_span     = 1
    row_span     = 1
    order        = 8
    downtime_only = False

    # ── JS ──────────────────────────────────────────────────
    js_inline = None

    def process(self) -> WidgetResult:
        df = self.df
        total_weight = 0.0

        if not df.empty and "product_weight" in df.columns:
            if "area_type" in df.columns:
                total_weight = float(
                    df[df["area_type"] == "output"]["product_weight"].sum()
                )
            else:
                total_weight = float(df["product_weight"].sum())

        unit = self.ctx.config.get("unit", "kg")

        return self._result(
            "kpi",
            {"value": round(total_weight, 2), "unit": unit, "trend": None},
            category="kpi",
        )
