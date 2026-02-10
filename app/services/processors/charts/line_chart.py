"""
Line Chart Processor — production over time, per product.

SRP: This module is solely responsible for building the line-chart
     API response, including downtime annotation overlays.
"""

from __future__ import annotations

from typing import Dict, Any, List, TYPE_CHECKING

import pandas as pd

from app.services.processors.helpers import empty_widget, format_time_labels
from app.services.processors.charts.common import (
    FALLBACK_PALETTE,
    alpha,
    get_freq,
    find_nearest_label_index,
)
from app.core.cache import metadata_cache

if TYPE_CHECKING:
    from app.services.dashboard_data_service import DashboardData
    from app.services.widgets.aggregators import DataAggregator


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
    - ``downtime_events`` — list of downtime periods for annotation overlay
      (only when show_downtime=True and downtime data is available)
    """
    df = data.detections
    if df.empty:
        return empty_widget(widget_id, name, wtype)

    interval = data.params.interval
    curve_type = getattr(data.params, "curve_type", "smooth")
    show_downtime = getattr(data.params, "show_downtime", False)
    freq = get_freq(interval)

    # Ensure datetime
    if "detected_at" in df.columns:
        df["detected_at"] = pd.to_datetime(df["detected_at"])

    # ── Per-product resampled series ─────────────────────────────
    products = df["product_name"].unique() if "product_name" in df.columns else []

    # Build a FULL time index covering the entire queried range
    # so gaps with zero detections are visible on the chart.
    effective_start, effective_end = data.params.get_effective_datetimes()
    if effective_start and effective_end:
        full_index = pd.date_range(start=effective_start, end=effective_end, freq=freq)
    else:
        full_index = None

    global_series = df.set_index("detected_at").resample(freq).size()
    if global_series.empty:
        return empty_widget(widget_id, name, wtype)

    # Reindex to full range if available — fills leading/trailing gaps with 0
    if full_index is not None and len(full_index) > 0:
        global_series = global_series.reindex(full_index, fill_value=0)

    labels = format_time_labels(global_series.index, interval)

    datasets = _build_datasets(df, products, global_series, freq, curve_type)

    # ── Class breakdown per time bucket (for tooltips) ───────────
    class_details = _build_class_details(df, freq, interval)

    # ── Downtime events for chart annotation overlay ─────────────
    downtime_events = _build_downtime_events(data, show_downtime, global_series)

    response_data: Dict[str, Any] = {
        "labels": labels,
        "datasets": datasets,
        "curve_type": curve_type,
        "class_details": class_details,
    }
    if downtime_events:
        response_data["downtime_events"] = downtime_events

    return {
        "widget_id": widget_id,
        "widget_name": name,
        "widget_type": wtype,
        "data": response_data,
        "metadata": {
            "widget_category": "chart",
            "total_points": len(global_series),
            "show_downtime": show_downtime,
            "downtime_count": len(downtime_events),
        },
    }


# ── Private helpers ──────────────────────────────────────────────────

def _build_datasets(
    df: pd.DataFrame,
    products,
    global_series: pd.Series,
    freq: str,
    curve_type: str,
) -> List[Dict[str, Any]]:
    """Build one dataset per product (or a single aggregate dataset)."""
    stacked = curve_type == "stacked"
    datasets: List[Dict[str, Any]] = []

    if len(products) > 1:
        for idx, prod in enumerate(sorted(products)):
            prod_df = df[df["product_name"] == prod]
            color = (
                prod_df["product_color"].iloc[0]
                if "product_color" in prod_df.columns
                else FALLBACK_PALETTE[idx % len(FALLBACK_PALETTE)]
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
                "backgroundColor": alpha(color, 0.25 if stacked else 0.08),
                "fill": stacked,
            })
    else:
        color = "#3b82f6"
        if "product_color" in df.columns and not df["product_color"].empty:
            color = df["product_color"].iloc[0]
        datasets.append({
            "label": products[0] if len(products) == 1 else "Producción",
            "data": global_series.values.tolist(),
            "borderColor": color,
            "backgroundColor": alpha(color, 0.1),
            "fill": True,
        })

    return datasets


def _build_class_details(
    df: pd.DataFrame, freq: str, interval: str
) -> Dict[str, Dict[str, int]]:
    """Per-time-bucket product breakdown used for rich tooltips."""
    class_details: Dict[str, Dict[str, int]] = {}
    if "product_name" not in df.columns:
        return class_details

    fmt_map = {
        "minute": "%H:%M",
        "15min": "%d/%m %H:%M",
        "hour": "%d/%m %H:%M",
        "day": "%d/%m/%Y",
        "week": "Sem %d/%m",
        "month": "%b %Y",
    }
    fmt = fmt_map.get(interval, "%d/%m %H:%M")

    grouped = (
        df.set_index("detected_at")
        .groupby([pd.Grouper(freq=freq), "product_name"])
        .size()
        .unstack(fill_value=0)
    )
    for ts, row in grouped.iterrows():
        label_key = ts.strftime(fmt)
        breakdown = {k: int(v) for k, v in row.items() if v > 0}
        if breakdown:
            class_details[label_key] = breakdown

    return class_details


def _build_downtime_events(
    data: "DashboardData",
    show_downtime: bool,
    global_series: pd.Series,
) -> List[Dict[str, Any]]:
    """Build downtime annotation events for the line chart overlay."""
    if not show_downtime or not data.has_downtime:
        return []

    dt_df = data.downtime
    label_list = list(global_series.index)
    incidents = metadata_cache.get_incidents()
    events: List[Dict[str, Any]] = []

    for _, evt in dt_df.iterrows():
        evt_start = pd.to_datetime(evt.get("start_time"))
        evt_end = pd.to_datetime(evt.get("end_time"))
        if pd.isna(evt_start) or pd.isna(evt_end):
            continue

        start_idx = find_nearest_label_index(label_list, evt_start)
        end_idx = find_nearest_label_index(label_list, evt_end)
        duration_min = round(evt.get("duration", 0) / 60.0, 1)

        reason_code = evt.get("reason_code")
        has_incident = pd.notna(reason_code) and reason_code
        incident = incidents.get(int(reason_code)) if has_incident else None
        desc = incident["description"] if incident else ""

        events.append({
            "xMin": start_idx,
            "xMax": end_idx,
            "start_time": evt_start.strftime("%H:%M"),
            "end_time": evt_end.strftime("%H:%M"),
            "duration_min": duration_min,
            "reason": desc,
            "has_incident": bool(has_incident),
            "source": evt.get("source", "db"),
            "line_name": evt.get("line_name", ""),
        })

    return events
