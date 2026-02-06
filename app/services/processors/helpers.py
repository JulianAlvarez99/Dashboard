"""
Shared helpers for widget processors.

Contains utility functions used across KPI, chart, and table processors:
- Empty widget response builder
- Time label formatting
- Scheduled minutes calculation
- Shift duration calculation
- Widget type inference
- Area type helpers
"""

from typing import Dict, List, Any, Optional
from datetime import timedelta
import unicodedata

from app.core.cache import metadata_cache
from app.services.widgets.base import FilterParams


def empty_widget(widget_id: int, name: str, wtype: str) -> Dict[str, Any]:
    """Build a standard empty-widget response."""
    return {
        "widget_id": widget_id,
        "widget_name": name,
        "widget_type": wtype,
        "data": None,
        "metadata": {"empty": True, "message": "No hay datos disponibles"},
    }


def format_time_labels(index, interval: str) -> List[str]:
    """Format a pandas DatetimeIndex to human-readable labels."""
    fmt_map = {
        "minute": "%H:%M",
        "15min": "%d/%m %H:%M",
        "hour": "%d/%m %H:%M",
        "day": "%d/%m/%Y",
        "week": "Sem %d/%m",
        "month": "%b %Y",
    }
    fmt = fmt_map.get(interval, "%d/%m %H:%M")
    return [idx.strftime(fmt) for idx in index]


# ─── Scheduling / shift helpers ──────────────────────────────────────

def calculate_scheduled_minutes(params: FilterParams) -> float:
    """
    Total scheduled production time in minutes.

    If a shift is selected, only that shift's hours count.
    Otherwise all active shifts are summed.
    The result is multiplied by the number of calendar days in the range.
    """
    shifts = metadata_cache.get_shifts()

    if params.shift_id:
        shift = shifts.get(params.shift_id)
        if not shift:
            return 0.0
        selected = [shift]
    else:
        selected = list(shifts.values())

    if not selected:
        return 0.0

    daily = sum(_get_shift_duration_minutes(s) for s in selected)
    if daily <= 0:
        return 0.0

    effective_start, effective_end = params.get_effective_datetimes()
    if effective_start and effective_end:
        num_days = (effective_end.date() - effective_start.date()).days + 1
    elif params.start_date and params.end_date:
        num_days = (params.end_date - params.start_date).days + 1
    else:
        num_days = 1

    return daily * max(1, num_days)


def _get_shift_duration_minutes(shift: dict) -> float:
    """Duration of a single shift in minutes (handles timedelta & time objects)."""
    start = shift.get("start_time")
    end = shift.get("end_time")
    is_overnight = shift.get("is_overnight", False)

    if start is None or end is None:
        return 0.0

    start_m = _to_minutes(start)
    end_m = _to_minutes(end)
    if start_m is None or end_m is None:
        return 0.0

    if is_overnight or end_m <= start_m:
        return (24.0 * 60.0 - start_m) + end_m
    return end_m - start_m


def _to_minutes(value) -> Optional[float]:
    """Convert a timedelta or time-like object to total minutes."""
    if isinstance(value, timedelta):
        return value.total_seconds() / 60.0
    if hasattr(value, "hour"):
        return value.hour * 60 + value.minute
    return None


# ─── Area helpers ────────────────────────────────────────────────────

def get_lines_with_input_output(line_ids: List[int]) -> List[int]:
    """
    Return only line IDs that have BOTH 'input' and 'output' areas.
    Lines with a single area (e.g. Bolsa25kg only has 'output') cannot
    be used for quality or descarte calculations.
    """
    result = []
    for lid in line_ids:
        areas = metadata_cache.get_areas_by_line(lid)
        types = {a["area_type"] for a in areas}
        if "input" in types and "output" in types:
            result.append(lid)
    return result


# ─── Widget-type inference ───────────────────────────────────────────

def strip_accents(text: str) -> str:
    """Remove accents/diacritics for matching. e.g. Producción → Produccion"""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.category(c).startswith("M"))


def infer_widget_type(widget_name: str) -> str:
    """Infer widget type from its display name (accent-insensitive)."""
    name = strip_accents(widget_name).lower()

    # KPI widgets
    if "kpi" in name:
        if "oee" in name:               return "kpi_oee"
        if "disponibilidad" in name:     return "kpi_availability"
        if "rendimiento" in name:        return "kpi_performance"
        if "calidad" in name:            return "kpi_quality"
        if "produccion" in name:         return "kpi_total_production"
        if "peso" in name:               return "kpi_total_weight"
        if "parada" in name:             return "kpi_downtime_count"

    # Table widgets
    if "tabla" in name or "table" in name:
        return "downtime_table"

    # Chart widgets
    if "comparacion" in name or "comparativa" in name or "comparison" in name:
        return "comparison_bar"
    if "distribucion" in name or "torta" in name or "pie" in name:
        return "pie_chart"
    if "detecciones por area" in name or "barra" in name or "bar" in name:
        return "bar_chart"
    if "produccion por tiempo" in name or "temporal" in name:
        return "line_chart"

    # Fallback patterns
    if "produccion" in name and "total" in name:
        return "kpi_total_production"
    if "peso" in name:
        return "kpi_total_weight"
    if "parada" in name:
        return "kpi_downtime_count"

    return "unknown"
