"""
Comparison Bar Processor — Entrada vs Salida vs Descarte over time.

SRP: This module is solely responsible for building the comparison-bar
     API response (input / output / discard time-series).
"""

from __future__ import annotations

from typing import Dict, Any, TYPE_CHECKING

import pandas as pd

from app.services.processors.helpers import (
    empty_widget,
    format_time_labels,
    get_lines_with_input_output,
)
from app.services.processors.charts.common import get_freq

if TYPE_CHECKING:
    from app.services.dashboard_data_service import DashboardData
    from app.services.widgets.aggregators import DataAggregator


def process_comparison_bar(
    widget_id: int,
    name: str,
    wtype: str,
    data: "DashboardData",
    aggregator: "DataAggregator",
) -> Dict[str, Any]:
    """
    Comparison: Entrada vs Salida vs Descarte over time.

    Uses the same aggregation interval as the line chart so both
    widgets have consistent time axes.
    Descarte = Entrada − Salida per time bucket (only dual-area lines).
    """
    df = data.detections
    if df.empty or "area_type" not in df.columns:
        return empty_widget(widget_id, name, wtype)

    interval = data.params.interval
    freq = get_freq(interval)

    df["detected_at"] = pd.to_datetime(df["detected_at"])

    # Identify dual-area lines
    dual_lines = get_lines_with_input_output(data.lines_queried)

    # Only keep relevant records (input/output)
    relevant = df[df["area_type"].isin(["input", "output"])]
    if relevant.empty:
        return empty_widget(widget_id, name, wtype)

    # ── Build per-interval series ────────────────────────────────
    output_series = (
        relevant[relevant["area_type"] == "output"]
        .set_index("detected_at")
        .resample(freq)
        .size()
    )

    if dual_lines and "line_id" in relevant.columns:
        dual_df = relevant[relevant["line_id"].isin(dual_lines)]
        input_series = (
            dual_df[dual_df["area_type"] == "input"]
            .set_index("detected_at")
            .resample(freq)
            .size()
        )
        output_dual_series = (
            dual_df[dual_df["area_type"] == "output"]
            .set_index("detected_at")
            .resample(freq)
            .size()
        )
    else:
        input_series = pd.Series(dtype=int)
        output_dual_series = pd.Series(dtype=int)

    # Build full time index covering the entire queried range
    effective_start, effective_end = data.params.get_effective_datetimes()
    if effective_start and effective_end:
        full_index = pd.date_range(start=effective_start, end=effective_end, freq=freq)
    else:
        full_index = None

    # Unify index
    all_idx = output_series.index
    if not input_series.empty:
        all_idx = all_idx.union(input_series.index)
    if not output_dual_series.empty:
        all_idx = all_idx.union(output_dual_series.index)
    all_idx = all_idx.sort_values()

    # Reindex to full temporal window
    if full_index is not None and len(full_index) > 0:
        all_idx = full_index

    if all_idx.empty:
        return empty_widget(widget_id, name, wtype)

    entrada_vals = (
        input_series.reindex(all_idx, fill_value=0)
        if not input_series.empty
        else pd.Series(0, index=all_idx)
    )
    salida_vals = output_series.reindex(all_idx, fill_value=0)
    if not output_dual_series.empty:
        descarte_vals = (
            input_series.reindex(all_idx, fill_value=0)
            - output_dual_series.reindex(all_idx, fill_value=0)
        ).clip(lower=0)
    else:
        descarte_vals = pd.Series(0, index=all_idx)

    labels = format_time_labels(all_idx, interval)

    total_entrada = int(entrada_vals.sum())
    total_salida = int(salida_vals.sum())
    total_descarte = int(descarte_vals.sum())

    return {
        "widget_id": widget_id,
        "widget_name": name,
        "widget_type": wtype,
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "label": "Entrada",
                    "data": entrada_vals.values.tolist(),
                    "backgroundColor": "#22c55e",
                },
                {
                    "label": "Salida",
                    "data": salida_vals.values.tolist(),
                    "backgroundColor": "#3b82f6",
                },
                {
                    "label": "Descarte",
                    "data": descarte_vals.values.tolist(),
                    "backgroundColor": "#ef4444",
                },
            ],
            "summary": {
                "entrada": total_entrada,
                "salida": total_salida,
                "descarte": total_descarte,
            },
        },
        "metadata": {"widget_category": "chart", "total_points": len(all_idx)},
    }
