"""
ResponseAssembler — Packages widget results into the final JSON.

Single Responsibility: take raw widget output dicts and shape them
into the response contract expected by the frontend.

Output schema::

    {
        "widgets": { "<widget_id>": { ...widget result... }, ... },
        "metadata": {
            "total_detections": int,
            "total_downtime_events": int,
            "lines_queried": [int, ...],
            "is_multi_line": bool,
            "widget_count": int,
            "period": {"start": str, "end": str},
            "interval": str,
            "elapsed_seconds": float,
            "timestamp": str,
            "error": str | None,
            # Only present when include_raw=True:
            "shift_windows": { "<shift_id>": {name, start, end, planned_seconds, is_overnight} },
            "line_config":   { "<line_id>":  {line_name, availability, performance} },
        },
        # Only present when include_raw=True:
        "raw_data":     [ {detected_at, line_id, area_id, area_type,
                           product_id, product_name, product_code,
                           product_color, product_weight, shift_id}, ... ],
        "raw_downtime": [ {start_time, end_time, duration, reason_code,
                           line_id, source, is_manual}, ... ],
    }
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from new_app.core.cache import metadata_cache
from new_app.services.orchestrator.context import DashboardContext


# Columns extracted from the detections DataFrame for raw_data
_RAW_DETECTION_COLS = [
    "detected_at",
    "line_id",
    "area_id",
    "area_type",
    "product_id",
    "product_name",
    "product_code",
    "product_color",
    "product_weight",
    "shift_id",
]

# Columns extracted from the downtime DataFrame for raw_downtime
_RAW_DOWNTIME_COLS = [
    "start_time",
    "end_time",
    "duration",        # seconds (float)
    "reason_code",
    "line_id",
    "source",
    "is_manual",
]


class ResponseAssembler:
    """Stateless helper that builds the dashboard JSON response."""

    @staticmethod
    def assemble(
        ctx: DashboardContext,
        widgets_result: List[Dict[str, Any]],
        elapsed: float,
        raw_df: Optional[pd.DataFrame] = None,
        downtime_df: Optional[pd.DataFrame] = None,
    ) -> Dict[str, Any]:
        """
        Package widget results + metadata into the final response.

        Args:
            ctx:             The populated DashboardContext.
            widgets_result:  List of serialized WidgetResult dicts.
            elapsed:         Total pipeline duration in seconds.
            raw_df:          Optional raw detections DataFrame (include_raw mode).
            downtime_df:     Optional raw downtime DataFrame (include_raw mode).

        Returns:
            JSON-serializable dict.
        """
        widgets_dict = _index_widgets(widgets_result)
        period = _extract_period(ctx.cleaned)

        metadata: Dict[str, Any] = {
            "total_detections": ctx.total_detections,
            "total_downtime_events": ctx.total_downtime_events,
            "lines_queried": ctx.line_ids,
            "is_multi_line": ctx.is_multi_line,
            "widget_count": len(widgets_result),
            "period": period,
            "interval": ctx.cleaned.get("interval", "hour"),
            "elapsed_seconds": round(elapsed, 3),
            "timestamp": datetime.now().isoformat(),
        }

        response: Dict[str, Any] = {
            "widgets": widgets_dict,
            "metadata": metadata,
        }

        # ── Raw data (only when include_raw=True) ─────────────────
        if raw_df is not None and not raw_df.empty:
            response["raw_data"] = _serialize_detections(raw_df)
            response["raw_downtime"] = (
                _serialize_downtime(downtime_df)
                if downtime_df is not None and not downtime_df.empty
                else []
            )
            # Enrich metadata with shift_windows and line_config
            metadata["shift_windows"] = _build_shift_windows()
            metadata["line_config"] = _build_line_config(ctx.line_ids)

        return response

    @staticmethod
    def empty(error: str = "") -> Dict[str, Any]:
        """
        Return a valid-but-empty response when the pipeline
        cannot proceed (no lines, no widgets, etc.).
        """
        return {
            "widgets": {},
            "metadata": {
                "total_detections": 0,
                "total_downtime_events": 0,
                "lines_queried": [],
                "is_multi_line": False,
                "widget_count": 0,
                "period": {},
                "interval": "hour",
                "elapsed_seconds": 0,
                "timestamp": datetime.now().isoformat(),
                "error": error,
            },
        }


# ── Private helpers ──────────────────────────────────────────────

def _index_widgets(widgets_result: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Convert the widget list into a keyed dict (widget_id → result)."""
    indexed: Dict[str, Any] = {}
    for w in widgets_result:
        key = str(w.get("widget_id", w.get("widget_name", "unknown")))
        indexed[key] = w
    return indexed


def _extract_period(cleaned: Dict[str, Any]) -> Dict[str, str]:
    """Extract date/time period from the cleaned filter dict."""
    daterange = cleaned.get("daterange", {})
    if not isinstance(daterange, dict):
        return {}

    period: Dict[str, str] = {
        "start": daterange.get("start_date", ""),
        "end": daterange.get("end_date", ""),
    }
    if daterange.get("start_time"):
        period["start_time"] = daterange["start_time"]
    if daterange.get("end_time"):
        period["end_time"] = daterange["end_time"]

    return period


def _serialize_detections(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Serialize the raw detections DataFrame to a list of dicts.

    Only includes columns defined in ``_RAW_DETECTION_COLS``.
    Missing columns are silently omitted.
    Timestamps are converted to ISO-8601 strings.
    """
    cols = [c for c in _RAW_DETECTION_COLS if c in df.columns]
    subset = df[cols].copy()

    # Convert timestamps to ISO strings
    if "detected_at" in subset.columns:
        subset["detected_at"] = (
            pd.to_datetime(subset["detected_at"])
            .dt.strftime("%Y-%m-%dT%H:%M:%S")
        )

    # Convert floats to avoid JSON serialization issues with numpy types
    for col in ("product_weight",):
        if col in subset.columns:
            subset[col] = subset[col].astype(float)

    # Replace NaN/NaT with None
    subset = subset.where(pd.notna(subset), None)

    return subset.to_dict(orient="records")


def _serialize_downtime(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Serialize the raw downtime DataFrame to a list of dicts.

    Only includes columns defined in ``_RAW_DOWNTIME_COLS``.
    Missing columns are silently omitted.
    """
    cols = [c for c in _RAW_DOWNTIME_COLS if c in df.columns]
    subset = df[cols].copy()

    # Convert timestamps to ISO strings
    for col in ("start_time", "end_time"):
        if col in subset.columns:
            subset[col] = (
                pd.to_datetime(subset[col])
                .dt.strftime("%Y-%m-%dT%H:%M:%S")
            )

    # Ensure duration is a plain Python float
    if "duration" in subset.columns:
        subset["duration"] = subset["duration"].astype(float)

    subset = subset.where(pd.notna(subset), None)
    return subset.to_dict(orient="records")


def _build_shift_windows() -> Dict[str, Any]:
    """
    Build shift_windows metadata from the MetadataCache.

    Returned to the frontend so JS can slice raw_data by shift's
    time window without knowing the exact hours beforehand.

    Shape::

        {
            "1": {
                "name": "Mañana",
                "start": "06:00",
                "end": "14:00",
                "is_overnight": false,
                "planned_seconds": 28800      # 8 h
            },
            ...
        }
    """
    shifts = metadata_cache.get_shifts()
    result: Dict[str, Any] = {}

    for shift_id, shift in shifts.items():
        start = shift.get("start_time")
        end = shift.get("end_time")

        # start_time / end_time may be datetime.time objects or strings
        start_str = str(start)[:5] if start else "00:00"   # "HH:MM"
        end_str   = str(end)[:5]   if end   else "23:59"

        # Planned seconds: end - start (handle overnight)
        planned = _calc_planned_seconds(start_str, end_str)

        result[str(shift_id)] = {
            "name": shift.get("shift_name", f"Turno {shift_id}"),
            "start": start_str,
            "end": end_str,
            "is_overnight": bool(shift.get("is_overnight", False)),
            "planned_seconds": planned,
        }

    return result


def _calc_planned_seconds(start: str, end: str) -> int:
    """Calculate planned seconds between HH:MM strings (handles overnight)."""
    try:
        sh, sm = map(int, start.split(":"))
        eh, em = map(int, end.split(":"))
        start_mins = sh * 60 + sm
        end_mins   = eh * 60 + em
        if end_mins <= start_mins:          # overnight shift
            end_mins += 24 * 60
        return (end_mins - start_mins) * 60
    except (ValueError, AttributeError):
        return 28800    # fallback: 8 hours


def _build_line_config(line_ids: List[int]) -> Dict[str, Any]:
    """
    Build per-line config metadata (OEE rate factors).

    Returned so JS can compute Performance/Availability/Quality
    client-side when re-aggregating by shift.

    Shape::

        {
            "1": {
                "line_name": "Línea 1",
                "availability": 0.95,    # planned availability factor
                "performance": 0.90,     # ideal performance factor
                "downtime_threshold": 60,
            },
            ...
        }
    """
    lines = metadata_cache.get_production_lines()
    result: Dict[str, Any] = {}

    for lid in line_ids:
        line = lines.get(lid, {})
        result[str(lid)] = {
            "line_name": line.get("line_name", f"Line {lid}"),
            "availability": float(line.get("availability") or 0.95),
            "performance":  float(line.get("performance")  or 0.90),
            "downtime_threshold": line.get("downtime_threshold", 60),
        }

    return result
