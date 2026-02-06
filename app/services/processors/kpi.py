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
    - Performance  = Actual Output / Expected Output  (production_std)
    - Quality      = Output / Input  (only dual-area lines; defaults to 100 %)
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

        # ── Quality ──
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

        # ── Availability ──
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

        # ── Performance ──
        if "product_id" in df.columns and scheduled_minutes > 0:
            output_df = df[df["area_type"] == "output"]
            if not output_df.empty:
                most_common = output_df["product_id"].mode()
                if not most_common.empty:
                    pid = most_common.iloc[0]
                    prod_std = (
                        metadata_cache.get_products()
                        .get(pid, {})
                        .get("production_std", 0)
                    )
                    if prod_std > 0:
                        hours = (scheduled_minutes - total_downtime_minutes) / 60.0
                        expected = prod_std * hours
                        if expected > 0:
                            performance = min(
                                100.0, round((salida / expected) * 100, 1)
                            )

        # ── OEE ──
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
