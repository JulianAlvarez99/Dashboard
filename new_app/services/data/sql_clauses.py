"""
SQL clause builders — Pure functions for dynamic WHERE construction.

Single Responsibility: build individual SQL fragments (clauses, hints,
parameter bindings) from filter values.  No query orchestration, no
table resolution, no I/O.

These functions are consumed by ``QueryBuilder`` and can be reused by
any future module that needs to compose SQL dynamically.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from new_app.core.cache import metadata_cache

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────
#  TABLE REFERENCE
# ─────────────────────────────────────────────────────────────────

def table_with_hint(table_name: str, partition_hint: str = "") -> str:
    """Return ``table_name PARTITION (...)`` or just ``table_name``."""
    if partition_hint:
        return f"{table_name} {partition_hint}"
    return table_name


# ─────────────────────────────────────────────────────────────────
#  COMPOSITE: APPLY ALL COMMON FILTERS
# ─────────────────────────────────────────────────────────────────

def apply_filters(
    sql: str,
    params: Dict[str, Any],
    cleaned: Dict[str, Any],
    time_column: str = "detected_at",
) -> str:
    """
    Append all common WHERE clauses to a SQL string.

    Applies daterange, shift, area_ids, and product_ids in one call
    so query builders don't repeat the same 4-clause block.

    Args:
        sql:          SQL with an existing WHERE clause.
        params:       Mutable bind params dict (extended in place).
        cleaned:      Validated filter dict from FilterEngine.
        time_column:  Column for daterange/shift (default: ``detected_at``).

    Returns:
        SQL string with filter clauses appended.
    """
    sql = apply_daterange(sql, params, cleaned, time_column)

    shift = build_shift_clause(cleaned, params, time_column)
    if shift:
        sql += f" AND {shift}"

    areas = build_in_clause(cleaned.get("area_ids"), "area_id", "area", params)
    if areas:
        sql += f" AND {areas}"

    products = build_in_clause(cleaned.get("product_ids"), "product_id", "prod", params)
    if products:
        sql += f" AND {products}"

    return sql


# ─────────────────────────────────────────────────────────────────
#  DATERANGE
# ─────────────────────────────────────────────────────────────────

def apply_daterange(
    sql: str,
    params: Dict[str, Any],
    cleaned: Dict[str, Any],
    time_column: str = "detected_at",
) -> str:
    """
    Append ``time_column >= :start_dt AND time_column <= :end_dt``.

    Returns the SQL string unchanged if no valid daterange is present.
    """
    daterange = cleaned.get("daterange")
    if not daterange or not isinstance(daterange, dict):
        return sql

    start_dt, end_dt = parse_daterange(daterange)

    if start_dt:
        sql += f" AND {time_column} >= :start_dt"
        params["start_dt"] = start_dt
    if end_dt:
        sql += f" AND {time_column} <= :end_dt"
        params["end_dt"] = end_dt

    return sql


# ─────────────────────────────────────────────────────────────────
#  SHIFT (TIME-OF-DAY)
# ─────────────────────────────────────────────────────────────────

def build_shift_clause(
    cleaned: Dict[str, Any],
    params: Dict[str, Any],
    time_column: str = "detected_at",
) -> Optional[str]:
    """
    Build a ``TIME()`` clause for shift filtering.

    Handles overnight shifts (22:00→06:00) with OR logic
    and normal shifts (06:00→14:00) with AND logic.

    Returns ``None`` if no shift is selected.
    """
    shift_id = cleaned.get("shift_id")
    if not shift_id:
        return None

    shift = metadata_cache.get_shift(int(shift_id))
    if not shift:
        logger.warning(f"[sql_clauses] shift_id={shift_id} not in cache")
        return None

    s_str = time_to_str(shift.get("start_time"))
    e_str = time_to_str(shift.get("end_time"))
    if not s_str or not e_str:
        return None

    params["shift_start"] = s_str
    params["shift_end"] = e_str

    is_overnight = shift.get("is_overnight", False) or e_str <= s_str

    if is_overnight:
        return (
            f"(TIME({time_column}) >= :shift_start "
            f"OR TIME({time_column}) < :shift_end)"
        )
    return (
        f"TIME({time_column}) >= :shift_start "
        f"AND TIME({time_column}) < :shift_end"
    )


# ─────────────────────────────────────────────────────────────────
#  IN CLAUSE
# ─────────────────────────────────────────────────────────────────

def build_in_clause(
    values: Optional[List[Any]],
    column: str,
    prefix: str,
    params: Dict[str, Any],
) -> Optional[str]:
    """
    Build ``column IN (:prefix_0, :prefix_1, ...)``.

    Adds numbered bind params to *params* dict.
    Returns ``None`` if *values* is empty or ``None``.
    """
    if not values:
        return None
    placeholders = []
    for i, v in enumerate(values):
        key = f"{prefix}_{i}"
        placeholders.append(f":{key}")
        params[key] = v
    return f"{column} IN ({', '.join(placeholders)})"


# ─────────────────────────────────────────────────────────────────
#  PARSING HELPERS
# ─────────────────────────────────────────────────────────────────

def parse_daterange(
    daterange: Dict[str, str],
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Parse a daterange dict into ``(start_datetime, end_datetime)``.

    Expected keys: ``start_date``, ``end_date``, ``start_time?``, ``end_time?``
    """
    start_dt = _parse_bound(daterange, "start_date", "start_time", "00:00", 0)
    end_dt = _parse_bound(daterange, "end_date", "end_time", "23:59", 59)
    return start_dt, end_dt


def _parse_bound(
    daterange: Dict[str, str],
    date_key: str,
    time_key: str,
    default_time: str,
    extra_seconds: int,
) -> Optional[datetime]:
    """Parse one bound (start or end) of a daterange."""
    raw_date = daterange.get(date_key)
    if not raw_date:
        return None
    try:
        d = date.fromisoformat(raw_date)
        raw_time = daterange.get(time_key, default_time)
        parts = raw_time.split(":")
        h, m = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
        return datetime(d.year, d.month, d.day, h, m, extra_seconds)
    except (ValueError, TypeError):
        return None


def time_to_str(value: Any) -> Optional[str]:
    """Convert ``timedelta`` or ``time`` object to ``'HH:MM:SS'`` string."""
    if isinstance(value, timedelta):
        total = int(value.total_seconds())
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
    if hasattr(value, "hour"):
        return f"{value.hour:02d}:{value.minute:02d}:{value.second:02d}"
    return None
