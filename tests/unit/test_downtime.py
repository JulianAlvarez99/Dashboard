"""
Unit tests for calculate_gap_downtimes() in downtime_calculator.py.

Coverage:
  - Empty DataFrame returns empty result
  - No gap above threshold → no events
  - Gap exactly at threshold → no event (< strict)
  - Gap above threshold → one event
  - Consecutive gaps → one merged event
  - Auto-detect disabled → no events
  - threshold_override respected
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pandas as pd
import pytest

from new_app.services.data.downtime_calculator import (
    calculate_gap_downtimes,
    remove_overlapping,
)

MOCK_LINE_META = {
    "line_id": 1,
    "line_name": "Línea 1",
    "auto_detect_downtime": True,
    "downtime_threshold": 300,  # 5 minutes
}


def _patch_cache(line_meta=None):
    """Context manager that patches metadata_cache.get_production_line."""
    meta = line_meta or MOCK_LINE_META

    class _FakeCache:
        def get_production_line(self, lid):
            return meta if lid == 1 else None

    return patch(
        "new_app.services.data.downtime_calculator.metadata_cache",
        new=_FakeCache(),
    )


def _make_df(timestamps: list[datetime], line_id: int = 1) -> pd.DataFrame:
    return pd.DataFrame({
        "detected_at": [pd.Timestamp(t) for t in timestamps],
        "line_id": line_id,
    })


# ── Tests ────────────────────────────────────────────────────────

def test_empty_dataframe():
    """Empty input returns empty output."""
    with _patch_cache():
        result = calculate_gap_downtimes(pd.DataFrame(), [1])
    assert result.empty


def test_no_columns():
    """DataFrame without required columns returns empty."""
    df = pd.DataFrame({"x": [1, 2, 3]})
    with _patch_cache():
        result = calculate_gap_downtimes(df, [1])
    assert result.empty


def test_no_gap_above_threshold():
    """All gaps below threshold → no downtime events."""
    base = datetime(2025, 1, 1, 8, 0, 0)
    # 30-second gaps, threshold is 300 s
    times = [base + timedelta(seconds=i * 30) for i in range(10)]
    df = _make_df(times)
    with _patch_cache():
        result = calculate_gap_downtimes(df, [1])
    assert result.empty


def test_gap_exactly_at_threshold_no_event():
    """Gap == threshold is NOT > threshold → no event (strict >)."""
    base = datetime(2025, 1, 1, 8, 0, 0)
    # Two detections exactly 300 s apart
    times = [base, base + timedelta(seconds=300)]
    df = _make_df(times)
    with _patch_cache():
        result = calculate_gap_downtimes(df, [1])
    assert result.empty


def test_gap_above_threshold_one_event():
    """One gap > threshold → exactly one downtime event."""
    base = datetime(2025, 1, 1, 8, 0, 0)
    times = [
        base,
        base + timedelta(seconds=30),
        base + timedelta(seconds=60),
        base + timedelta(seconds=660),   # gap = 600 s > 300 s
        base + timedelta(seconds=690),
    ]
    df = _make_df(times)
    with _patch_cache():
        result = calculate_gap_downtimes(df, [1])

    assert len(result) == 1
    evt = result.iloc[0]
    assert evt["line_id"] == 1
    assert evt["source"] == "calculated"
    # Duration should be ~ 600 s (60 → 660)
    assert abs(evt["duration"] - 600) < 1


def test_consecutive_gaps_merged():
    """Two consecutive above-threshold gaps → one merged event."""
    base = datetime(2025, 1, 1, 8, 0, 0)
    times = [
        base,                            # t0
        base + timedelta(seconds=400),   # gap1 = 400 s (> 300)
        base + timedelta(seconds=800),   # gap2 = 400 s (> 300) — consecutive
        base + timedelta(seconds=830),   # resumes
    ]
    df = _make_df(times)
    with _patch_cache():
        result = calculate_gap_downtimes(df, [1])

    # Both consecutive gaps belong to the same event
    assert len(result) == 1
    evt = result.iloc[0]
    # Event spans from t0 to t2 = 800 s total
    assert abs(evt["duration"] - 800) < 1


def test_auto_detect_disabled():
    """auto_detect_downtime=False → no gap events regardless."""
    meta = {**MOCK_LINE_META, "auto_detect_downtime": False}
    base = datetime(2025, 1, 1, 8, 0, 0)
    times = [base, base + timedelta(seconds=600)]
    df = _make_df(times)
    with _patch_cache(line_meta=meta):
        result = calculate_gap_downtimes(df, [1])
    assert result.empty


def test_threshold_override():
    """threshold_override supersedes per-line DB value."""
    base = datetime(2025, 1, 1, 8, 0, 0)
    times = [base, base + timedelta(seconds=400)]  # gap = 400 s
    df = _make_df(times)
    # Default threshold 300 → would generate an event
    # Override to 500 → no event
    with _patch_cache():
        result = calculate_gap_downtimes(df, [1], threshold_override=500)
    assert result.empty


def test_remove_overlapping_keeps_non_overlapping():
    """Calculated events that don't overlap DB events are kept."""
    calc = pd.DataFrame([{
        "start_time": pd.Timestamp("2025-01-01 09:00"),
        "end_time":   pd.Timestamp("2025-01-01 09:10"),
        "duration": 600.0, "reason_code": None, "line_id": 1, "source": "calculated",
    }])
    db = pd.DataFrame([{
        "start_time": pd.Timestamp("2025-01-01 10:00"),
        "end_time":   pd.Timestamp("2025-01-01 10:30"),
        "duration": 1800.0, "reason_code": 1, "line_id": 1, "source": "db",
    }])
    result = remove_overlapping(calc, db)
    assert len(result) == 1


def test_remove_overlapping_drops_overlapping():
    """Calculated event overlapping a DB event is dropped."""
    calc = pd.DataFrame([{
        "start_time": pd.Timestamp("2025-01-01 09:55"),
        "end_time":   pd.Timestamp("2025-01-01 10:05"),
        "duration": 600.0, "reason_code": None, "line_id": 1, "source": "calculated",
    }])
    db = pd.DataFrame([{
        "start_time": pd.Timestamp("2025-01-01 10:00"),
        "end_time":   pd.Timestamp("2025-01-01 10:30"),
        "duration": 1800.0, "reason_code": 1, "line_id": 1, "source": "db",
    }])
    result = remove_overlapping(calc, db)
    assert result.empty
