"""Summary: Aggregated metrics across all queried lines."""

from __future__ import annotations

import pandas as pd

from new_app.services.widgets.base import BaseWidget, WidgetResult


class MetricsSummary(BaseWidget):

    def process(self) -> WidgetResult:
        df = self.df
        if df.empty:
            return self._empty("summary")

        total_detections = len(df)

        output_count = total_detections
        if "area_type" in df.columns:
            output_count = len(df[df["area_type"] == "output"])

        total_weight = 0.0
        if "product_weight" in df.columns:
            if "area_type" in df.columns:
                total_weight = float(
                    df[df["area_type"] == "output"]["product_weight"].sum()
                )
            else:
                total_weight = float(df["product_weight"].sum())

        df["detected_at"] = pd.to_datetime(df["detected_at"])
        first_detection = df["detected_at"].min()
        last_detection = df["detected_at"].max()
        hours_span = (last_detection - first_detection).total_seconds() / 3600.0

        avg_per_hour = round(output_count / hours_span, 1) if hours_span > 0 else 0

        unique_products = (
            df["product_name"].nunique() if "product_name" in df.columns else 0
        )

        lines_count = len(self.ctx.lines_queried)

        # Downtime info
        dt_df = self.downtime_df
        downtime_count = 0
        downtime_minutes = 0.0
        if not dt_df.empty:
            downtime_count = len(dt_df)
            if "duration" in dt_df.columns:
                downtime_minutes = round(dt_df["duration"].sum() / 60.0, 1)

        return self._result(
            "summary",
            {
                "total_detections": total_detections,
                "output_count": output_count,
                "total_weight": round(total_weight, 2),
                "avg_per_hour": avg_per_hour,
                "hours_span": round(hours_span, 1),
                "unique_products": unique_products,
                "lines_count": lines_count,
                "downtime_count": downtime_count,
                "downtime_minutes": downtime_minutes,
                "first_detection": first_detection.strftime("%Y-%m-%d %H:%M"),
                "last_detection": last_detection.strftime("%Y-%m-%d %H:%M"),
            },
            category="summary",
        )
