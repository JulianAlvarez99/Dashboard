"""
Pytest fixtures shared across all tests.

Provides:
  - sample_detections_df: small DataFrame mimicking enriched detection rows
  - sample_downtime_df:   small DataFrame mimicking downtime events
  - mock_cache:           a patched MetadataCache with synthetic metadata
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


# ── Sample detection data ────────────────────────────────────────

def _make_detections(
    line_id: int = 1,
    count: int = 10,
    interval_seconds: int = 30,
    start: datetime | None = None,
    area_type: str = "output",
) -> pd.DataFrame:
    """Build a synthetic detections DataFrame."""
    if start is None:
        start = datetime(2025, 1, 1, 8, 0, 0)
    rows = []
    for i in range(count):
        rows.append({
            "detection_id": i + 1,
            "line_id": line_id,
            "area_id": 1,
            "area_type": area_type,
            "product_id": 1,
            "detected_at": start + timedelta(seconds=i * interval_seconds),
        })
    return pd.DataFrame(rows)


@pytest.fixture
def sample_detections_df():
    """10 detections on line 1, spaced 30 seconds apart — no gap events."""
    return _make_detections(line_id=1, count=10, interval_seconds=30)


@pytest.fixture
def sample_detections_with_gap():
    """
    Detections on line 1 with one large gap (> threshold).

    Gap between detection 5 and detection 6: 600 seconds (10 minutes).
    Threshold configured in mock_cache_meta: 300 s.
    """
    start = datetime(2025, 1, 1, 8, 0, 0)
    rows = []
    t = start
    for i in range(5):
        rows.append({
            "detection_id": i + 1,
            "line_id": 1,
            "area_id": 1,
            "area_type": "output",
            "product_id": 1,
            "detected_at": t,
        })
        t += timedelta(seconds=30)

    # Large gap (10 min = 600 s > threshold 300 s)
    t += timedelta(seconds=600)

    for i in range(5):
        rows.append({
            "detection_id": i + 6,
            "line_id": 1,
            "area_id": 1,
            "area_type": "output",
            "product_id": 1,
            "detected_at": t,
        })
        t += timedelta(seconds=30)

    return pd.DataFrame(rows)


@pytest.fixture
def sample_downtime_df():
    """Two downtime events on line 1."""
    return pd.DataFrame([
        {
            "start_time": datetime(2025, 1, 1, 9, 0, 0),
            "end_time":   datetime(2025, 1, 1, 9, 15, 0),
            "duration":   900.0,
            "reason_code": None,
            "line_id": 1,
            "source": "calculated",
        },
        {
            "start_time": datetime(2025, 1, 1, 10, 0, 0),
            "end_time":   datetime(2025, 1, 1, 10, 30, 0),
            "duration":   1800.0,
            "reason_code": 1,
            "line_id": 1,
            "source": "db",
        },
    ])


# ── Mock MetadataCache ───────────────────────────────────────────

MOCK_LINE_META = {
    1: {
        "line_id": 1,
        "line_name": "Línea 1",
        "line_code": "L1",
        "is_active": True,
        "availability": 90.0,
        "performance": 2.0,       # 2 outputs / operating minute
        "downtime_threshold": 300,  # 5 minutes
        "auto_detect_downtime": True,
    }
}


@pytest.fixture
def mock_cache():
    """Patch MetadataCache with synthetic single-line metadata."""
    with patch("new_app.core.cache.metadata_cache") as mc:
        mc.get_production_line.side_effect = lambda lid: MOCK_LINE_META.get(lid)
        mc.get_production_lines.return_value = MOCK_LINE_META
        mc.get_active_line_ids.return_value = [1]
        mc.get_areas.return_value = {}
        mc.get_shifts.return_value = {}
        mc.is_loaded = True
        yield mc
