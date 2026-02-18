"""
Chart: Production over time — per-product line chart with downtime overlay.

The most complex chart widget.  Features:
  - One dataset per product (colored by product_color).
  - Full time index with fill_value=0 (no gaps).
  - class_details per bucket for rich tooltips.
  - Optional downtime annotation overlay.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from new_app.core.cache import metadata_cache
from new_app.services.widgets.base import BaseWidget, WidgetResult
from new_app.services.widgets.helpers import (
    FALLBACK_PALETTE,
    TIME_LABEL_FORMATS,
    alpha,
    find_nearest_label_index,
    format_time_labels,
    get_freq,
)


class ProductionTimeChart(BaseWidget):

    def process(self) -> WidgetResult:
        df = self.df
        if df.empty:
            return self._empty("chart")

        interval = self.ctx.params.get("interval", "hour")
        curve_type = self.ctx.config.get("curve_type", "smooth")
        show_downtime = self.ctx.params.get("show_downtime", False)
        freq = get_freq(interval)

        if "detected_at" in df.columns:
            df["detected_at"] = pd.to_datetime(df["detected_at"])

        products = (
            df["product_name"].unique()
            if "product_name" in df.columns
            else []
        )

        # Full time index covering the queried range
        full_index = self._build_full_index(freq)

        global_series = df.set_index("detected_at").resample(freq).size()
        if global_series.empty:
            return self._empty("chart")

        if full_index is not None and len(full_index) > 0:
            global_series = global_series.reindex(full_index, fill_value=0)

        labels = format_time_labels(global_series.index, interval)

        datasets = self._build_datasets(df, products, global_series, freq, curve_type)
        class_details = self._build_class_details(df, freq, interval)
        downtime_events = self._build_downtime_overlay(
            show_downtime, global_series,
        )

        response_data: Dict[str, Any] = {
            "labels": labels,
            "datasets": datasets,
            "curve_type": curve_type,
            "class_details": class_details,
        }
        if downtime_events:
            response_data["downtime_events"] = downtime_events

        return self._result(
            "chart",
            response_data,
            category="chart",
            total_points=len(global_series),
            show_downtime=show_downtime,
            downtime_count=len(downtime_events),
        )

    # ── Private helpers ──────────────────────────────────────────

    def _build_full_index(self, freq: str):
        """Build date_range from the queried daterange params."""
        daterange = self.ctx.params.get("daterange", {})
        sd = daterange.get("start_date")
        ed = daterange.get("end_date")
        st = daterange.get("start_time")
        et = daterange.get("end_time")
        if sd and ed:
            try:
                start_str = f"{sd} {st}" if st else sd
                end_str = f"{ed} {et}" if et else ed
                return pd.date_range(start=start_str, end=end_str, freq=freq)
            except Exception:
                pass
        return None

    @staticmethod
    def _build_datasets(
        df: pd.DataFrame,
        products,
        global_series: pd.Series,
        freq: str,
        curve_type: str,
    ) -> List[Dict[str, Any]]:
        stacked = curve_type == "stacked"
        datasets: List[Dict[str, Any]] = []

        if len(products) > 1:
            for idx, prod in enumerate(sorted(products)):
                prod_df = df[df["product_name"] == prod]
                color = (
                    prod_df["product_color"].iloc[0]
                    if "product_color" in prod_df.columns
                    and not prod_df["product_color"].empty
                    else FALLBACK_PALETTE[idx % len(FALLBACK_PALETTE)]
                )
                series = (
                    prod_df.set_index("detected_at")
                    .resample(freq)
                    .size()
                    .reindex(global_series.index, fill_value=0)
                )
                datasets.append({
                    "label": prod,
                    "data": series.values.tolist(),
                    "borderColor": color,
                    "backgroundColor": alpha(color, 0.25 if stacked else 0.08),
                    "fill": stacked,
                })
        else:
            color = "#3b82f6"
            if "product_color" in df.columns and not df["product_color"].empty:
                color = df["product_color"].iloc[0]
            datasets.append({
                "label": products[0] if len(products) == 1 else "Producción",
                "data": global_series.values.tolist(),
                "borderColor": color,
                "backgroundColor": alpha(color, 0.1),
                "fill": True,
            })

        return datasets

    @staticmethod
    def _build_class_details(
        df: pd.DataFrame, freq: str, interval: str,
    ) -> Dict[str, Dict[str, int]]:
        """Per-time-bucket product breakdown for tooltips."""
        if "product_name" not in df.columns:
            return {}

        fmt = TIME_LABEL_FORMATS.get(interval, "%d/%m %H:%M")

        grouped = (
            df.set_index("detected_at")
            .groupby([pd.Grouper(freq=freq), "product_name"])
            .size()
            .unstack(fill_value=0)
        )
        class_details: Dict[str, Dict[str, int]] = {}
        for ts, row in grouped.iterrows():
            label_key = ts.strftime(fmt)
            breakdown = {k: int(v) for k, v in row.items() if v > 0}
            if breakdown:
                class_details[label_key] = breakdown

        return class_details

    def _build_downtime_overlay(
        self,
        show_downtime: bool,
        global_series: pd.Series,
    ) -> List[Dict[str, Any]]:
        """Downtime annotation events for the line chart overlay."""
        if not show_downtime or not self.has_downtime:
            return []

        dt_df = self.downtime_df
        label_list = list(global_series.index)
        incidents = metadata_cache.get_incidents()
        events: List[Dict[str, Any]] = []

        for _, evt in dt_df.iterrows():
            evt_start = pd.to_datetime(evt.get("start_time"))
            evt_end = pd.to_datetime(evt.get("end_time"))
            if pd.isna(evt_start) or pd.isna(evt_end):
                continue

            start_idx = find_nearest_label_index(label_list, evt_start)
            end_idx = find_nearest_label_index(label_list, evt_end)
            duration_min = round(evt.get("duration", 0) / 60.0, 1)

            reason_code = evt.get("reason_code")
            has_incident = pd.notna(reason_code) and bool(reason_code)
            incident = incidents.get(int(reason_code)) if has_incident else None
            desc = incident["description"] if incident else ""

            events.append({
                "xMin": start_idx,
                "xMax": end_idx,
                "start_time": evt_start.strftime("%H:%M"),
                "end_time": evt_end.strftime("%H:%M"),
                "duration_min": duration_min,
                "reason": desc,
                "has_incident": bool(has_incident),
                "source": evt.get("source", "db"),
                "line_name": evt.get("line_name", ""),
            })

        return events
