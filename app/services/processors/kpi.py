"""
KPI Processors — one function per KPI widget type.

Each processor receives (widget_id, name, wtype, data)
and returns a Dict[str, Any] ready for the API response.
"""

from __future__ import annotations

from typing import Dict, Any, TYPE_CHECKING

from app.core.cache import metadata_cache
from app.services.processors.helpers import (
    calculate_scheduled_minutes,
    get_lines_with_input_output,
)

if TYPE_CHECKING:
    from app.services.dashboard_data_service import DashboardData


# ─── Production ──────────────────────────────────────────────────────

def process_kpi_production(
    widget_id: int, name: str, wtype: str, data: DashboardData
) -> Dict[str, Any]:
    """Total production count = number of 'output' detections across all lines."""
    df = data.detections
    if not df.empty and "area_type" in df.columns:
        value = int(len(df[df["area_type"] == "output"]))
    else:
        value = len(df)

    return {
        "widget_id": widget_id,
        "widget_name": name,
        "widget_type": wtype,
        "data": {"value": value, "unit": "unidades", "trend": None},
        "metadata": {"widget_category": "kpi"},
    }


# ─── Weight ──────────────────────────────────────────────────────────

def process_kpi_weight(
    widget_id: int, name: str, wtype: str, data: DashboardData
) -> Dict[str, Any]:
    """Total weight of production (output area only)."""
    df = data.detections
    total_weight = 0.0

    if not df.empty and "product_weight" in df.columns:
        if "area_type" in df.columns:
            total_weight = float(
                df[df["area_type"] == "output"]["product_weight"].sum()
            )
        else:
            total_weight = float(df["product_weight"].sum())

    return {
        "widget_id": widget_id,
        "widget_name": name,
        "widget_type": wtype,
        "data": {"value": round(total_weight, 2), "unit": "kg", "trend": None},
        "metadata": {"widget_category": "kpi"},
    }


# ─── OEE (Availability × Performance × Quality) ─────────────────────

def process_kpi_oee(
    widget_id: int, name: str, wtype: str, data: DashboardData
) -> Dict[str, Any]:
    """
    OEE = A × P × Q

    - Availability = (Scheduled – Downtime) / Scheduled
        • Scheduled = sum of shift intervals × days in range.
        • Downtime  = merged DB + gap-calculated events (DB has priority
          over calculated when intervals overlap — already handled
          upstream by ``remove_overlapping``).

    - Performance = Real Output / Theoretical Output
        • Theoretical = production_line.performance (products/min)
                        × operating minutes (scheduled – downtime).
        • Real        = total output detections for that line.
        When multiple lines are queried the theoretical output is
        summed per-line so each line contributes its own rate.

    - Quality = Output / Input  (only for lines with both areas)
        • Lines with a single area default to 100 %.
    """
    df = data.detections
    downtime_df = data.downtime

    availability = 0.0
    performance = 0.0
    quality = 0.0
    oee = 0.0
    scheduled_minutes = 0.0
    total_downtime_minutes = 0.0

    if not df.empty and "area_type" in df.columns:
        salida = len(df[df["area_type"] == "output"])

        # ── Quality ──────────────────────────────────────────────
        # For lines with input + output areas: quality = output / input.
        # For lines with only one area: quality = 100 %.
        dual_lines = get_lines_with_input_output(data.lines_queried)
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

        # ── Availability ─────────────────────────────────────────
        # Scheduled time = shift durations × calendar days.
        # Downtime already de-duplicated (DB events take priority).
        scheduled_minutes = calculate_scheduled_minutes(data.params)
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

        # ── Performance ──────────────────────────────────────────
        # Uses production_line.performance (products/min) per line.
        # Theoretical = Σ(line.performance × operating_minutes) per line.
        # Real        = total output detections across all queried lines.
        operating_minutes = max(0.0, scheduled_minutes - total_downtime_minutes)
        if operating_minutes > 0 and "line_id" in df.columns:
            total_expected = 0.0
            for lid in data.lines_queried:
                line_meta = metadata_cache.get_production_line(lid)
                if not line_meta:
                    continue
                # performance = products per minute (from PRODUCTION_LINE table)
                perf_rate = line_meta.get("performance", 0) or 0
                if perf_rate <= 0:
                    continue

                # Per-line downtime (minutes)
                line_dt_min = 0.0
                if not downtime_df.empty and "line_id" in downtime_df.columns:
                    line_dt = downtime_df[downtime_df["line_id"] == lid]
                    if not line_dt.empty and "duration" in line_dt.columns:
                        line_dt_min = line_dt["duration"].sum() / 60.0

                line_op_min = max(0.0, scheduled_minutes - line_dt_min)
                total_expected += perf_rate * line_op_min

            if total_expected > 0:
                performance = min(
                    100.0, round((salida / total_expected) * 100, 1)
                )

        # ── OEE ──────────────────────────────────────────────────
        if availability > 0 and performance > 0 and quality > 0:
            oee = round(
                (availability / 100) * (performance / 100) * (quality / 100) * 100,
                1,
            )

    return {
        "widget_id": widget_id,
        "widget_name": name,
        "widget_type": wtype,
        "data": {
            "value": oee,
            "unit": "%",
            "availability": availability,
            "performance": performance,
            "quality": quality,
            "scheduled_minutes": round(scheduled_minutes, 1),
            "downtime_minutes": round(total_downtime_minutes, 1),
            "trend": None,
        },
        "metadata": {"widget_category": "kpi"},
    }


# ─── Downtime count ─────────────────────────────────────────────────

def process_kpi_downtime(
    widget_id: int, name: str, wtype: str, data: DashboardData
) -> Dict[str, Any]:
    """Count and total duration of downtime events."""
    downtime_df = data.downtime
    count = 0
    total_minutes = 0.0

    if not downtime_df.empty:
        count = len(downtime_df)
        if "duration" in downtime_df.columns:
            total_minutes = round(downtime_df["duration"].sum() / 60.0, 1)

    return {
        "widget_id": widget_id,
        "widget_name": name,
        "widget_type": wtype,
        "data": {
            "value": count,
            "unit": "paradas",
            "total_minutes": total_minutes,
            "trend": None,
        },
        "metadata": {"widget_category": "kpi"},
    }


# ─── Derived KPIs (delegate to OEE to avoid duplicating logic) ──────

def process_kpi_availability(
    widget_id: int, name: str, wtype: str, data: DashboardData
) -> Dict[str, Any]:
    oee = process_kpi_oee(widget_id, name, "kpi_oee", data)
    return {
        "widget_id": widget_id,
        "widget_name": name,
        "widget_type": wtype,
        "data": {
            "value": oee["data"]["availability"],
            "unit": "%",
            "scheduled_minutes": oee["data"].get("scheduled_minutes", 0),
            "downtime_minutes": oee["data"].get("downtime_minutes", 0),
            "trend": None,
        },
        "metadata": {"widget_category": "kpi"},
    }


def process_kpi_performance(
    widget_id: int, name: str, wtype: str, data: DashboardData
) -> Dict[str, Any]:
    oee = process_kpi_oee(widget_id, name, "kpi_oee", data)
    return {
        "widget_id": widget_id,
        "widget_name": name,
        "widget_type": wtype,
        "data": {"value": oee["data"]["performance"], "unit": "%", "trend": None},
        "metadata": {"widget_category": "kpi"},
    }


def process_kpi_quality(
    widget_id: int, name: str, wtype: str, data: DashboardData
) -> Dict[str, Any]:
    oee = process_kpi_oee(widget_id, name, "kpi_oee", data)
    return {
        "widget_id": widget_id,
        "widget_name": name,
        "widget_type": wtype,
        "data": {"value": oee["data"]["quality"], "unit": "%", "trend": None},
        "metadata": {"widget_category": "kpi"},
    }
