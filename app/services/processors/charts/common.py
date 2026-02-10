"""
Shared constants and utilities for chart processors.

DRY: colour palettes and helpers live here once,
imported by each individual chart module.
"""

from __future__ import annotations

from typing import List

import pandas as pd


# ─── Colour palettes ────────────────────────────────────────────────

FALLBACK_PALETTE = [
    "#3b82f6", "#22c55e", "#ef4444", "#f59e0b",
    "#8b5cf6", "#ec4899", "#14b8a6", "#f97316",
]

BAR_PALETTE = [
    "#3b82f6", "#22c55e", "#ef4444", "#f59e0b",
    "#8b5cf6", "#ec4899", "#14b8a6", "#f97316",
]


# ─── Helpers ─────────────────────────────────────────────────────────

def alpha(hex_color: str, a: float = 0.15) -> str:
    """Convert '#RRGGBB' → 'rgba(r,g,b,a)'."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return f"rgba(100,100,100,{a})"
    r, g, b = int(h[:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{a})"


# ─── Interval / frequency mapping ───────────────────────────────────

INTERVAL_FREQ_MAP = {
    "minute": "1min",
    "15min": "15min",
    "hour": "1h",
    "day": "1D",
    "week": "1W",
    "month": "1ME",
}


def get_freq(interval: str) -> str:
    """Return a pandas-compatible frequency string for the given interval."""
    return INTERVAL_FREQ_MAP.get(interval, "1h")


def find_nearest_label_index(
    label_list: List[pd.Timestamp], target: pd.Timestamp
) -> int:
    """Find the index of the nearest timestamp in *label_list* to *target*."""
    if not label_list:
        return 0
    if target <= label_list[0]:
        return 0
    if target >= label_list[-1]:
        return len(label_list) - 1
    idx = pd.Index(label_list).get_indexer([target], method="nearest")[0]
    return int(idx)
