"""
Chart Processors — line, bar, pie, and comparison-bar widgets.

Each processor receives (widget_id, name, wtype, data, aggregator)
and returns a Dict[str, Any] ready for the API response.
"""

from __future__ import annotations

from typing import Dict, Any, List, TYPE_CHECKING

import pandas as pd

from app.services.processors.helpers import (
    empty_widget,
    format_time_labels,
    get_lines_with_input_output,
)

if TYPE_CHECKING:
    from app.services.dashboard_data_service import DashboardData
    from app.services.widgets.aggregators import DataAggregator


# ─── Colour helpers ──────────────────────────────────────────────────

_FALLBACK_PALETTE = [
    "#3b82f6", "#22c55e", "#ef4444", "#f59e0b",
    "#8b5cf6", "#ec4899", "#14b8a6", "#f97316",
]


def _alpha(hex_color: str, alpha: float = 0.15) -> str:
    """Convert '#RRGGBB' → 'rgba(r,g,b,a)'."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return f"rgba(100,100,100,{alpha})"
    r, g, b = int(h[:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


# ─── Line Chart (production over time, per product) ─────────────────

def process_line_chart(
    widget_id: int,
    name: str,
    wtype: str,
    data: "DashboardData",
    aggregator: "DataAggregator",
) -> Dict[str, Any]:
    """
    Production over time as a line chart with one dataset per product.

    The response includes:
    - ``curve_type`` so the frontend knows how to style the line
    - ``class_details`` — per-time-point breakdown of detected classes
      keyed by label string, used for rich tooltips
    """
    df = data.detections
    if df.empty:
        return empty_widget(widget_id, name, wtype)

    interval = data.params.interval
    curve_type = getattr(data.params, "curve_type", "smooth")

    # Ensure datetime
    if "detected_at" in df.columns:
        df["detected_at"] = pd.to_datetime(df["detected_at"])

    # ── Per-product resampled series ─────────────────────────────
    products = df["product_name"].unique() if "product_name" in df.columns else []
    interval_map = {
        "minute": "1min", "15min": "15min", "hour": "1h",
        "day": "1D", "week": "1W", "month": "1ME",
    }
    freq = interval_map.get(interval, "1h")

    # Build a full time index from the global resampled series
    global_series = df.set_index("detected_at").resample(freq).size()
    if global_series.empty:
        return empty_widget(widget_id, name, wtype)

    labels = format_time_labels(global_series.index, interval)

    datasets: List[Dict[str, Any]] = []
    stacked = curve_type == "stacked"

    if len(products) > 1:
        for idx, prod in enumerate(sorted(products)):
            prod_df = df[df["product_name"] == prod]
            # Get the product colour from the first row (already enriched)
            color = (
                prod_df["product_color"].iloc[0]
                if "product_color" in prod_df.columns
                else _FALLBACK_PALETTE[idx % len(_FALLBACK_PALETTE)]
            )
            series = (
                prod_df.set_index("detected_at")
                .resample(freq)
                .size()
                .reindex(global_series.index, fill_value=0)
            )
            datasets.append({
                "label": prod,
                "data": series.values.tolist(),
                "borderColor": color,
                "backgroundColor": _alpha(color, 0.25 if stacked else 0.08),
                "fill": stacked,
            })
    else:
        # Single product (or no product column) — one dataset
        color = "#3b82f6"
        if "product_color" in df.columns and not df["product_color"].empty:
            color = df["product_color"].iloc[0]
        datasets.append({
            "label": products[0] if len(products) == 1 else "Producción",
            "data": global_series.values.tolist(),
            "borderColor": color,
            "backgroundColor": _alpha(color, 0.1),
            "fill": True,
        })

    # ── Class breakdown per time bucket (for tooltips) ───────────
    class_details: Dict[str, Dict[str, int]] = {}
    if "product_name" in df.columns:
        grouped = (
            df.set_index("detected_at")
            .groupby([pd.Grouper(freq=freq), "product_name"])
            .size()
            .unstack(fill_value=0)
        )
        for ts, row in grouped.iterrows():
            label_key = ts.strftime(
                {
                    "minute": "%H:%M",
                    "15min": "%d/%m %H:%M",
                    "hour": "%d/%m %H:%M",
                    "day": "%d/%m/%Y",
                    "week": "Sem %d/%m",
                    "month": "%b %Y",
                }.get(interval, "%d/%m %H:%M")
            )
            breakdown = {k: int(v) for k, v in row.items() if v > 0}
            if breakdown:
                class_details[label_key] = breakdown

    return {
        "widget_id": widget_id,
        "widget_name": name,
        "widget_type": wtype,
        "data": {
            "labels": labels,
            "datasets": datasets,
            "curve_type": curve_type,
            "class_details": class_details,
        },
        "metadata": {
            "widget_category": "chart",
            "total_points": len(global_series),
        },
    }


# ─── Bar Chart (distribution by area) ───────────────────────────────

_BAR_PALETTE = [
    "#3b82f6", "#22c55e", "#ef4444", "#f59e0b",
    "#8b5cf6", "#ec4899", "#14b8a6", "#f97316",
]


def process_bar_chart(
    widget_id: int,
    name: str,
    wtype: str,
    data: "DashboardData",
    aggregator: "DataAggregator",
) -> Dict[str, Any]:
    """Distribution by area as a bar chart."""
    df = data.detections
    if df.empty or "area_name" not in df.columns:
        return empty_widget(widget_id, name, wtype)

    series = aggregator.aggregate_by_column(df, "area_name", ascending=False)

    return {
        "widget_id": widget_id,
        "widget_name": name,
        "widget_type": wtype,
        "data": {
            "labels": series.index.tolist(),
            "datasets": [
                {
                    "label": "Detecciones por Área",
                    "data": series.values.tolist(),
                    "backgroundColor": _BAR_PALETTE[: len(series)],
                }
            ],
        },
        "metadata": {"widget_category": "chart", "total_points": len(series)},
    }


# ─── Pie Chart (distribution by product) ────────────────────────────

def process_pie_chart(
    widget_id: int,
    name: str,
    wtype: str,
    data: "DashboardData",
    aggregator: "DataAggregator",
) -> Dict[str, Any]:
    """Distribution by product as a pie chart."""
    df = data.detections
    if df.empty or "product_name" not in df.columns:
        return empty_widget(widget_id, name, wtype)

    grouped = (
        df.groupby(["product_name", "product_color"])
        .size()
        .reset_index(name="count")
    )

    return {
        "widget_id": widget_id,
        "widget_name": name,
        "widget_type": wtype,
        "data": {
            "labels": grouped["product_name"].tolist(),
            "datasets": [
                {
                    "data": grouped["count"].tolist(),
                    "backgroundColor": grouped["product_color"].tolist(),
                }
            ],
        },
        "metadata": {"widget_category": "chart", "total_points": len(grouped)},
    }


# ─── Comparison Bar (time-series: Entrada vs Salida vs Descarte) ────

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
    interval_map = {
        "minute": "1min", "15min": "15min", "hour": "1h",
        "day": "1D", "week": "1W", "month": "1ME",
    }
    freq = interval_map.get(interval, "1h")

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

    # For input we only consider dual-area lines
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

    # Unify index
    all_idx = output_series.index
    if not input_series.empty:
        all_idx = all_idx.union(input_series.index)
    if not output_dual_series.empty:
        all_idx = all_idx.union(output_dual_series.index)
    all_idx = all_idx.sort_values()

    if all_idx.empty:
        return empty_widget(widget_id, name, wtype)

    entrada_vals = input_series.reindex(all_idx, fill_value=0) if not input_series.empty else pd.Series(0, index=all_idx)
    salida_vals = output_series.reindex(all_idx, fill_value=0)
    if not output_dual_series.empty:
        descarte_vals = (
            input_series.reindex(all_idx, fill_value=0)
            - output_dual_series.reindex(all_idx, fill_value=0)
        ).clip(lower=0)
    else:
        descarte_vals = pd.Series(0, index=all_idx)

    labels = format_time_labels(all_idx, interval)

    # Summary totals
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
