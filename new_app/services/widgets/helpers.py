"""
Shared helpers for widget processors.

Single Responsibility: reusable utility functions consumed by
multiple widget types.  No widget-specific logic here.

Ported from ``app/services/processors/helpers.py`` with SRP cleanup.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List, Optional

from new_app.core.cache import metadata_cache


# ── Scheduling / shift helpers ───────────────────────────────────

def calculate_scheduled_minutes(cleaned: Dict[str, Any]) -> float:
    """
    Total scheduled production time in minutes.

    If a shift is selected, only that shift's hours count.
    Otherwise all active shifts are summed.
    The result is multiplied by the number of calendar days in the range.
    """
    shifts = metadata_cache.get_shifts()

    shift_id = cleaned.get("shift_id")
    if shift_id:
        shift = shifts.get(int(shift_id))
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

    num_days = _count_days(cleaned)
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
    """Convert a timedelta, time-like, or string object to total minutes."""
    if isinstance(value, timedelta):
        return value.total_seconds() / 60.0
    if hasattr(value, "hour"):
        return value.hour * 60 + value.minute
    # Handle string like "08:00:00" or "08:00"
    if isinstance(value, str):
        parts = value.split(":")
        try:
            hours = int(parts[0])
            minutes = int(parts[1]) if len(parts) > 1 else 0
            return hours * 60 + minutes
        except (ValueError, IndexError):
            return None
    return None


def _count_days(cleaned: Dict[str, Any]) -> int:
    """Count calendar days from the daterange filter."""
    daterange = cleaned.get("daterange")
    if not daterange or not isinstance(daterange, dict):
        return 1
    sd = daterange.get("start_date")
    ed = daterange.get("end_date")
    if not sd or not ed:
        return 1
    from datetime import date as date_type
    try:
        start = date_type.fromisoformat(sd) if isinstance(sd, str) else sd
        end = date_type.fromisoformat(ed) if isinstance(ed, str) else ed
        return max(1, (end - start).days + 1)
    except (ValueError, TypeError):
        return 1


# ── Area helpers ─────────────────────────────────────────────────

def get_lines_with_input_output(line_ids: List[int]) -> List[int]:
    """
    Return only line IDs that have BOTH 'input' and 'output' areas.

    Lines with a single area (e.g. only 'output') cannot be used
    for quality or descarte calculations.
    """
    result = []
    for lid in line_ids:
        areas = metadata_cache.get_areas_by_line(lid)
        types = {a["area_type"] for a in areas}
        if "input" in types and "output" in types:
            result.append(lid)
    return result


# ── Time formatting ──────────────────────────────────────────────

TIME_LABEL_FORMATS = {
    "minute": "%H:%M",
    "15min": "%d/%m %H:%M",
    "hour": "%d/%m %H:%M",
    "day": "%d/%m/%Y",
    "week": "Sem %d/%m",
    "month": "%b %Y",
}

INTERVAL_FREQ_MAP = {
    "minute": "1min",
    "15min": "15min",
    "hour": "1h",
    "day": "1D",
    "week": "1W",
    "month": "1ME",
}


def format_time_labels(index, interval: str) -> List[str]:
    """Format a pandas DatetimeIndex to human-readable labels."""
    fmt = TIME_LABEL_FORMATS.get(interval, "%d/%m %H:%M")
    return [idx.strftime(fmt) for idx in index]


def get_freq(interval: str) -> str:
    """Return a pandas-compatible frequency string for the given interval."""
    return INTERVAL_FREQ_MAP.get(interval, "1h")


# ── Colour palettes ─────────────────────────────────────────────

FALLBACK_PALETTE = [
    "#3b82f6", "#22c55e", "#ef4444", "#f59e0b",
    "#8b5cf6", "#ec4899", "#14b8a6", "#f97316",
]


def alpha(hex_color: str, a: float = 0.15) -> str:
    """Convert '#RRGGBB' → 'rgba(r,g,b,a)'."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return f"rgba(100,100,100,{a})"
    r, g, b = int(h[:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{a})"


def find_nearest_label_index(
    label_list: list, target
) -> int:
    """Find the index of the nearest timestamp in *label_list* to *target*."""
    import pandas as pd
    if not label_list:
        return 0
    if target <= label_list[0]:
        return 0
    if target >= label_list[-1]:
        return len(label_list) - 1
    idx = pd.Index(label_list).get_indexer([target], method="nearest")[0]
    return int(idx)
