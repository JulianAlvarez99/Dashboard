"""
ResponseAssembler — Packages widget results into the final JSON.

Single Responsibility: take raw widget output dicts and shape them
into the response contract expected by the frontend.

Output schema::

    {
        "widgets": {
            "<widget_id>": { ...widget result... },
            ...
        },
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
        }
    }
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from new_app.services.orchestrator.context import DashboardContext


class ResponseAssembler:
    """Stateless helper that builds the dashboard JSON response."""

    @staticmethod
    def assemble(
        ctx: DashboardContext,
        widgets_result: List[Dict[str, Any]],
        elapsed: float,
    ) -> Dict[str, Any]:
        """
        Package widget results + metadata into the final response.

        Args:
            ctx:             The populated DashboardContext.
            widgets_result:  List of serialized WidgetResult dicts.
            elapsed:         Total pipeline duration in seconds.

        Returns:
            JSON-serializable dict.
        """
        widgets_dict = _index_widgets(widgets_result)
        period = _extract_period(ctx.cleaned)

        return {
            "widgets": widgets_dict,
            "metadata": {
                "total_detections": ctx.total_detections,
                "total_downtime_events": ctx.total_downtime_events,
                "lines_queried": ctx.line_ids,
                "is_multi_line": ctx.is_multi_line,
                "widget_count": len(widgets_result),
                "period": period,
                "interval": ctx.cleaned.get("interval", "hour"),
                "elapsed_seconds": round(elapsed, 3),
                "timestamp": datetime.now().isoformat(),
            },
        }

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
    """
    Convert the widget list into a keyed dict.

    Uses ``widget_id`` as key (falls back to ``widget_name``).
    """
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
