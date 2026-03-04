"""
Date utilities — shared helpers for parsing and normalizing date/time values.

Used throughout the codebase wherever date strings from user input or
database rows need consistent handling.
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Optional


# ── Constants ────────────────────────────────────────────────────

DATE_FMT = "%Y-%m-%d"
TIME_FMT = "%H:%M"
DATETIME_FMT = "%Y-%m-%d %H:%M:%S"


# ── Parsing ──────────────────────────────────────────────────────

def parse_date(value: str) -> Optional[date]:
    """
    Parse an ISO date string (``YYYY-MM-DD``) to a :class:`date`.

    Returns ``None`` on failure instead of raising.

    Examples::

        parse_date("2024-01-15")   → date(2024, 1, 15)
        parse_date("bad")          → None
    """
    try:
        return datetime.strptime(value, DATE_FMT).date()
    except (ValueError, TypeError):
        return None


def parse_time(value: str) -> Optional[time]:
    """
    Parse an ``HH:MM`` string to a :class:`time`.

    Returns ``None`` on failure.
    """
    try:
        return datetime.strptime(value, TIME_FMT).time()
    except (ValueError, TypeError):
        return None


def parse_datetime(value: str) -> Optional[datetime]:
    """
    Parse a ``YYYY-MM-DD HH:MM:SS`` string to a naive :class:`datetime`.

    Returns ``None`` on failure.
    """
    try:
        return datetime.strptime(value, DATETIME_FMT)
    except (ValueError, TypeError):
        return None


# ── Normalization ─────────────────────────────────────────────────

def ensure_utc(dt: datetime) -> datetime:
    """
    Return *dt* with UTC timezone attached.

    If *dt* is already timezone-aware the existing timezone is
    replaced (converted) to UTC.  Naive datetimes are assumed to
    already represent UTC and are simply made aware.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def now_utc() -> datetime:
    """Return the current UTC moment as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


# ── Formatting ────────────────────────────────────────────────────

def fmt_date(d: date) -> str:
    """Format a :class:`date` as ``YYYY-MM-DD``."""
    return d.strftime(DATE_FMT)


def fmt_datetime(dt: datetime) -> str:
    """Format a :class:`datetime` as ``YYYY-MM-DD HH:MM:SS``."""
    return dt.strftime(DATETIME_FMT)
