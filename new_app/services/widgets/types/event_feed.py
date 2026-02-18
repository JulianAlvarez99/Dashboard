"""
Feed: Recent events — latest detections and downtime events combined.

New widget (no old app equivalent). Shows a chronological feed of
recent activity across all queried lines.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from new_app.services.widgets.base import BaseWidget, WidgetResult


class EventFeed(BaseWidget):

    def process(self) -> WidgetResult:
        max_items = self.ctx.config.get("max_items", 50)

        events: List[Dict[str, Any]] = []

        # Add detection events
        df = self.df
        if not df.empty and "detected_at" in df.columns:
            df["detected_at"] = pd.to_datetime(df["detected_at"])
            recent = df.nlargest(max_items, "detected_at")

            for _, row in recent.iterrows():
                events.append({
                    "type": "detection",
                    "timestamp": row["detected_at"].strftime("%Y-%m-%d %H:%M:%S"),
                    "line_name": row.get("line_name", ""),
                    "area_name": row.get("area_name", ""),
                    "product_name": row.get("product_name", ""),
                })

        # Add downtime events
        dt_df = self.downtime_df
        if not dt_df.empty and "start_time" in dt_df.columns:
            dt_df["start_time"] = pd.to_datetime(dt_df["start_time"])
            for _, row in dt_df.iterrows():
                events.append({
                    "type": "downtime",
                    "timestamp": row["start_time"].strftime("%Y-%m-%d %H:%M:%S"),
                    "line_name": row.get("line_name", ""),
                    "duration_min": round(row.get("duration", 0) / 60.0, 1),
                    "source": row.get("source", "db"),
                })

        # Sort by timestamp descending and limit
        events.sort(key=lambda e: e["timestamp"], reverse=True)
        events = events[:max_items]

        return self._result(
            "feed",
            {"events": events, "total": len(events)},
            category="feed",
        )
