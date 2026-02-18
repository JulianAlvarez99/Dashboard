"""
KPI: OEE — Overall Equipment Effectiveness (Availability × Performance × Quality).

This is the *master* OEE calculator.  KpiAvailability, KpiPerformance, and
KpiQuality delegate to ``_compute_oee()`` to avoid duplicating
the scheduling / downtime / performance logic (DRY).
"""

from __future__ import annotations

from typing import Any, Dict, List

from new_app.core.cache import metadata_cache
from new_app.services.widgets.base import BaseWidget, WidgetContext, WidgetResult
from new_app.services.widgets.helpers import (
    calculate_scheduled_minutes,
    get_lines_with_input_output,
)


def _compute_oee(ctx: WidgetContext) -> Dict[str, Any]:
    """
    Core OEE calculation shared by KpiOee, KpiAvailability,
    KpiPerformance, and KpiQuality.

    Returns dict with: oee, availability, performance, quality,
    scheduled_minutes, downtime_minutes.
    """
    df = ctx.data if hasattr(ctx, "data") else None
    import pandas as pd
    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame()
    downtime_df = ctx.downtime if ctx.downtime is not None else pd.DataFrame()

    availability = 0.0
    performance = 0.0
    quality = 0.0
    oee = 0.0
    scheduled_minutes = 0.0
    total_downtime_minutes = 0.0

    if not df.empty and "area_type" in df.columns:
        salida = len(df[df["area_type"] == "output"])

        # ── Quality ──────────────────────────────────────────
        dual_lines = get_lines_with_input_output(ctx.lines_queried)
        if dual_lines and "line_id" in df.columns:
            dual_df = df[df["line_id"].isin(dual_lines)]
            entrada = len(dual_df[dual_df["area_type"] == "input"])
            salida_q = len(dual_df[dual_df["area_type"] == "output"])
            quality = (
                min(100.0, round((salida_q / entrada) * 100, 1))
                if entrada > 0
                else 100.0
            )
        else:
            quality = 100.0

        # ── Availability ─────────────────────────────────────
        scheduled_minutes = calculate_scheduled_minutes(ctx.params)
        if not downtime_df.empty and "duration" in downtime_df.columns:
            total_downtime_minutes = downtime_df["duration"].sum() / 60.0
        if scheduled_minutes > 0:
            availability = max(
                0.0,
                min(
                    100.0,
                    round(
                        ((scheduled_minutes - total_downtime_minutes) / scheduled_minutes) * 100,
                        1,
                    ),
                ),
            )

        # ── Performance ──────────────────────────────────────
        operating_minutes = max(0.0, scheduled_minutes - total_downtime_minutes)
        if operating_minutes > 0 and "line_id" in df.columns:
            total_expected = 0.0
            for lid in ctx.lines_queried:
                line_meta = metadata_cache.get_production_line(lid)
                if not line_meta:
                    continue
                perf_rate = line_meta.get("performance", 0) or 0
                if perf_rate <= 0:
                    continue

                line_dt_min = 0.0
                if not downtime_df.empty and "line_id" in downtime_df.columns:
                    line_dt = downtime_df[downtime_df["line_id"] == lid]
                    if not line_dt.empty and "duration" in line_dt.columns:
                        line_dt_min = line_dt["duration"].sum() / 60.0

                line_op_min = max(0.0, scheduled_minutes - line_dt_min)
                total_expected += perf_rate * line_op_min

            if total_expected > 0:
                performance = min(
                    100.0, round((salida / total_expected) * 100, 1),
                )

        # ── OEE ──────────────────────────────────────────────
        if availability > 0 and performance > 0 and quality > 0:
            oee = round(
                (availability / 100) * (performance / 100) * (quality / 100) * 100,
                1,
            )

    return {
        "oee": oee,
        "availability": availability,
        "performance": performance,
        "quality": quality,
        "scheduled_minutes": round(scheduled_minutes, 1),
        "downtime_minutes": round(total_downtime_minutes, 1),
    }


class KpiOee(BaseWidget):

    def process(self) -> WidgetResult:
        calc = _compute_oee(self.ctx)
        return self._result(
            "kpi",
            {
                "value": calc["oee"],
                "unit": "%",
                "availability": calc["availability"],
                "performance": calc["performance"],
                "quality": calc["quality"],
                "scheduled_minutes": calc["scheduled_minutes"],
                "downtime_minutes": calc["downtime_minutes"],
                "trend": None,
            },
            category="kpi",
        )
