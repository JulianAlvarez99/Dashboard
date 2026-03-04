"""
Unit tests for KpiOee._compute_oee() (kpi_oee.py).

Coverage:
  - Zero scheduled time → all zeros
  - All downtime (availability=0) → oee=0
  - 100% availability + performance + quality → oee=100%
  - Multi-line aggregation
  - Quality calculation with dual-camera lines
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from new_app.services.widgets.base import WidgetContext
from new_app.services.widgets.types.kpi_oee import _compute_oee


def _make_ctx(
    detections: pd.DataFrame | None = None,
    downtime: pd.DataFrame | None = None,
    lines_queried: list[int] | None = None,
    params: dict | None = None,
) -> WidgetContext:
    ctx = WidgetContext(
        widget_id=1,
        widget_name="KpiOee",
        display_name="OEE",
        data=detections if detections is not None else pd.DataFrame(),
        downtime=downtime if downtime is not None else pd.DataFrame(),
        lines_queried=lines_queried or [1],
        params=params or {},
    )
    return ctx


MOCK_LINE = {
    "line_id": 1,
    "line_name": "Línea 1",
    "auto_detect_downtime": True,
    "downtime_threshold": 300,
    "performance": 2.0,
    "availability": 90.0,
}


def _patch_oee_deps(
    line_meta: dict | None = None,
    scheduled_minutes: float = 480.0,
    dual_lines: list[int] | None = None,
):
    """Helper: patch cache + schedule helpers for _compute_oee()."""
    meta = line_meta or MOCK_LINE
    return (
        patch(
            "new_app.services.widgets.types.kpi_oee.metadata_cache.get_production_line",
            side_effect=lambda lid: meta if lid == 1 else None,
        ),
        patch(
            "new_app.services.widgets.types.kpi_oee.calculate_scheduled_minutes",
            return_value=scheduled_minutes,
        ),
        patch(
            "new_app.services.widgets.types.kpi_oee.get_lines_with_input_output",
            return_value=dual_lines or [],
        ),
    )


def test_oee_zero_scheduled_time():
    """When scheduled time is 0, all metrics must be 0.0."""
    df = pd.DataFrame([{"area_type": "output", "line_id": 1}])
    ctx = _make_ctx(detections=df)

    p1, p2, p3 = _patch_oee_deps(scheduled_minutes=0.0)
    with p1, p2, p3:
        result = _compute_oee(ctx)

    assert result["oee"] == 0.0
    assert result["availability"] == 0.0
    assert result["performance"] == 0.0


def test_oee_empty_detections():
    """Empty detection DataFrame → all zeros."""
    ctx = _make_ctx(detections=pd.DataFrame())

    p1, p2, p3 = _patch_oee_deps()
    with p1, p2, p3:
        result = _compute_oee(ctx)

    assert result["oee"] == 0.0
    assert result["availability"] == 0.0


def test_oee_all_downtime():
    """When downtime == scheduled time, availability=0 and oee=0."""
    df = pd.DataFrame([{"area_type": "output", "line_id": 1}])
    # 480 minutes of downtime on 480 minutes scheduled = 0% availability
    downtime = pd.DataFrame([{
        "line_id": 1, "duration": 480.0 * 60,  # in seconds
    }])
    ctx = _make_ctx(detections=df, downtime=downtime)

    p1, p2, p3 = _patch_oee_deps(scheduled_minutes=480.0)
    with p1, p2, p3:
        result = _compute_oee(ctx)

    assert result["availability"] == 0.0
    assert result["oee"] == 0.0


def test_oee_100_percent():
    """Perfect conditions: no downtime, performance exactly at standard, no defects."""
    # performance = 2 outputs/min, scheduled = 60 min → expected 120 outputs
    scheduled = 60.0
    outputs = 120

    rows = [{"area_type": "output", "line_id": 1} for _ in range(outputs)]
    df = pd.DataFrame(rows)
    ctx = _make_ctx(detections=df, downtime=pd.DataFrame(), lines_queried=[1])

    p1, p2, p3 = _patch_oee_deps(scheduled_minutes=scheduled)
    with p1, p2, p3:
        result = _compute_oee(ctx)

    assert result["availability"] == 100.0
    assert result["performance"] == 100.0
    assert result["quality"] == 100.0
    assert result["oee"] == 100.0


def test_oee_multiline_aggregation():
    """Multiple lines: each line contributes to total expected output."""
    meta_line2 = {**MOCK_LINE, "line_id": 2, "line_name": "Línea 2", "performance": 2.0}
    # 2 lines × 2 op/min × 60 min = 240 expected outputs for 100% performance.
    # Provide 120 outputs (60 per line) → 120/240 = 50% performance.
    rows = (
        [{"area_type": "output", "line_id": 1} for _ in range(60)]
        + [{"area_type": "output", "line_id": 2} for _ in range(60)]
    )
    df = pd.DataFrame(rows)
    ctx = _make_ctx(detections=df, lines_queried=[1, 2])

    def _get_line(lid):
        return MOCK_LINE if lid == 1 else meta_line2

    with (
        patch("new_app.services.widgets.types.kpi_oee.metadata_cache.get_production_line",
              side_effect=_get_line),
        patch("new_app.services.widgets.types.kpi_oee.calculate_scheduled_minutes",
              return_value=60.0),
        patch("new_app.services.widgets.types.kpi_oee.get_lines_with_input_output",
              return_value=[]),
    ):
        result = _compute_oee(ctx)

    # 120 actual / 240 expected = 50%
    assert result["performance"] == 50.0
    assert result["availability"] == 100.0


def test_oee_quality_with_dual_line():
    """Lines with input+output: quality = output / input."""
    # 10 inputs, 8 outputs → quality = 80%
    rows = (
        [{"area_type": "input",  "line_id": 1} for _ in range(10)]
        + [{"area_type": "output", "line_id": 1} for _ in range(8)]
    )
    df = pd.DataFrame(rows)
    ctx = _make_ctx(detections=df, lines_queried=[1])

    p1, p2, p3 = _patch_oee_deps(scheduled_minutes=60.0, dual_lines=[1])
    with p1, p2, p3:
        result = _compute_oee(ctx)

    assert result["quality"] == 80.0
