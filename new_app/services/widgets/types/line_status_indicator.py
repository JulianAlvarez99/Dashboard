"""Indicator: Real-time status of each production line."""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from new_app.core.cache import metadata_cache
from new_app.services.widgets.base import BaseWidget, WidgetResult


class LineStatusIndicator(BaseWidget):

    def process(self) -> WidgetResult:
        df = self.df
        if df.empty or "line_name" not in df.columns:
            return self._empty("indicator")

        df["detected_at"] = pd.to_datetime(df["detected_at"])
        now = pd.Timestamp.now()

        lines_info: List[Dict[str, Any]] = []
        for line_id in self.ctx.lines_queried:
            line_meta = metadata_cache.get_production_line(line_id)
            if not line_meta:
                continue

            line_name = line_meta["line_name"]
            line_df = (
                df[df["line_id"] == line_id]
                if "line_id" in df.columns
                else df
            )

            count = len(line_df)
            if count > 0:
                last_detection = line_df["detected_at"].max()
                minutes_since = (now - last_detection).total_seconds() / 60.0
                status = "active" if minutes_since < 10 else "idle"
                last_dt_str = last_detection.strftime("%Y-%m-%d %H:%M")
            else:
                status = "no_data"
                last_dt_str = "\u2014"
                minutes_since = None

            output_count = count
            if "area_type" in line_df.columns:
                output_count = len(line_df[line_df["area_type"] == "output"])

            lines_info.append({
                "line_id": line_id,
                "line_name": line_name,
                "line_code": line_meta.get("line_code", ""),
                "status": status,
                "detection_count": count,
                "output_count": output_count,
                "last_detection": last_dt_str,
                "minutes_since_last": (
                    round(minutes_since, 1) if minutes_since is not None else None
                ),
            })

        return self._result(
            "indicator",
            {"lines": lines_info, "total_lines": len(lines_info)},
            category="status",
            total_lines=len(lines_info),
        )
