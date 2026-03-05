"""
KpiWeightEfficiency — Actual produced weight as a % of the theoretical weight.

Formula:
    weight_per_unit  = product_weight of any output detection (all same product)
    theoretical_kg   = performance_rate (u/min) × scheduled_minutes × weight_per_unit
    actual_kg        = output_count × weight_per_unit
    efficiency       = actual_kg / theoretical_kg × 100
"""

from __future__ import annotations

from new_app.core.cache import metadata_cache
from new_app.services.widgets.base import BaseWidget, WidgetResult
from new_app.services.widgets.helpers import calculate_queried_minutes


class KpiWeightEfficiency(BaseWidget):

    required_columns = ["area_type", "product_weight", "line_id"]
    default_config   = {}

    # ── Render ──────────────────────────────────────────────
    render       = "kpi"
    chart_type   = ""
    chart_height = "250px"

    # ── Layout ──────────────────────────────────────────────
    tab           = "produccion"
    col_span      = 1
    row_span      = 1
    order         = 17
    downtime_only = False

    # ── JS ──────────────────────────────────────────────────
    js_inline = None

    def process(self) -> WidgetResult:
        df  = self.df
        ctx = self.ctx

        output_df = df[df["area_type"] == "output"] if (
            not df.empty and "area_type" in df.columns
        ) else df

        # ── Weight per unit: first non-null product_weight in output rows ──
        weight_per_unit = 0.0
        if not output_df.empty and "product_weight" in output_df.columns:
            series = output_df["product_weight"].dropna()
            if not series.empty:
                weight_per_unit = float(series.iloc[0])

        # Fallback to metadata cache if no detections carry the weight
        if weight_per_unit <= 0:
            products = metadata_cache.get_products()
            for p in products.values():
                w = p.get("product_weight") or 0
                if w > 0:
                    weight_per_unit = float(w)
                    break

        # ── Actual weight: output count × weight per unit ─────────────────
        output_count  = len(output_df) if not output_df.empty else 0
        actual_weight = output_count * weight_per_unit

        # ── Theoretical weight: Σ per line (perf_rate × sched_min × w/u) ──
        scheduled_min      = calculate_queried_minutes(ctx.params)
        theoretical_weight = 0.0

        if scheduled_min > 0 and weight_per_unit > 0:
            line_meta = metadata_cache.get_production_line(ctx.lines_queried[0]) if ctx.lines_queried else None
            perf_rate = line_meta.get("performance") or 0  # units / min
            theoretical_weight = perf_rate * scheduled_min * weight_per_unit

        # ── Efficiency % ─────────────────────────────────────────────────
        if theoretical_weight > 0:
            efficiency = round(min(100.0, (actual_weight / theoretical_weight) * 100), 1)
        else:
            efficiency = 0.0

        return self._result(
            "kpi",
            {
                "value":                 efficiency,
                "unit":                  "%",
                "actual_weight_kg":      round(actual_weight, 2),
                "theoretical_weight_kg": round(theoretical_weight, 2),
                "trend":                 None,
            },
            category="kpi",
        )
