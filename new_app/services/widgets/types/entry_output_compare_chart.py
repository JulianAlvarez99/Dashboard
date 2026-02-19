"""Chart: Entrada vs Salida vs Descarte — comparison bar over time."""

from __future__ import annotations

from typing import Any, Dict

import pandas as pd

from new_app.core.cache import metadata_cache
from new_app.services.widgets.base import BaseWidget, WidgetResult
from new_app.services.widgets.helpers import (
    format_time_labels,
    get_freq,
    get_lines_with_input_output,
)


class EntryOutputCompareChart(BaseWidget):

    def process(self) -> WidgetResult:
        df = self.df
        if df.empty or "area_type" not in df.columns:
            return self._empty("chart")

        interval = self.ctx.params.get("interval", "hour")
        freq = get_freq(interval)

        df["detected_at"] = pd.to_datetime(df["detected_at"])

        dual_lines = get_lines_with_input_output(self.ctx.lines_queried)

        relevant = df[df["area_type"].isin(["input", "output"])]
        if relevant.empty:
            return self._empty("chart")

        # Per-interval series
        output_series = (
            relevant[relevant["area_type"] == "output"]
            .set_index("detected_at").resample(freq).size()
        )

        input_series = pd.Series(dtype=int)
        output_dual_series = pd.Series(dtype=int)

        if dual_lines and "line_id" in relevant.columns:
            dual_df = relevant[relevant["line_id"].isin(dual_lines)]
            input_series = (
                dual_df[dual_df["area_type"] == "input"]
                .set_index("detected_at").resample(freq).size()
            )
            output_dual_series = (
                dual_df[dual_df["area_type"] == "output"]
                .set_index("detected_at").resample(freq).size()
            )

        # Full time index
        full_index = self._build_full_index(freq)

        all_idx = output_series.index
        if not input_series.empty:
            all_idx = all_idx.union(input_series.index)
        if not output_dual_series.empty:
            all_idx = all_idx.union(output_dual_series.index)
        all_idx = all_idx.sort_values()

        if full_index is not None and len(full_index) > 0:
            all_idx = full_index

        if all_idx.empty:
            return self._empty("chart")

        entrada_vals = (
            input_series.reindex(all_idx, fill_value=0)
            if not input_series.empty
            else pd.Series(0, index=all_idx)
        )
        salida_vals = output_series.reindex(all_idx, fill_value=0)
        if not output_dual_series.empty:
            descarte_vals = (
                input_series.reindex(all_idx, fill_value=0)
                - output_dual_series.reindex(all_idx, fill_value=0)
            ).clip(lower=0)
        else:
            descarte_vals = pd.Series(0, index=all_idx)

        labels = format_time_labels(all_idx, interval)

        return self._result(
            "chart",
            {
                "labels": labels,
                "datasets": [
                    {
                        "label": "Entrada",
                        "data": entrada_vals.values.tolist(),
                        "backgroundColor": "#22c55e",
                    },
                    {
                        "label": "Salida",
                        "data": salida_vals.values.tolist(),
                        "backgroundColor": "#3b82f6",
                    },
                    {
                        "label": "Descarte",
                        "data": descarte_vals.values.tolist(),
                        "backgroundColor": "#ef4444",
                    },
                ],
                "summary": {
                    "entrada": int(entrada_vals.sum()),
                    "salida": int(salida_vals.sum()),
                    "descarte": int(descarte_vals.sum()),
                },
            },
            category="chart",
            total_points=len(all_idx),
        )

    def _build_full_index(self, freq: str):
        """Build date_range from the queried daterange params.

        When a shift is selected, the time window is adjusted to the
        shift's start/end times so the chart x-axis matches the shift.
        """
        daterange = self.ctx.params.get("daterange", {})
        sd = daterange.get("start_date")
        ed = daterange.get("end_date")
        st = daterange.get("start_time", "00:00")
        et = daterange.get("end_time", "23:59")

        # Adjust to shift window if a shift is selected
        shift_id = self.ctx.params.get("shift_id")
        if shift_id:
            shift = metadata_cache.get_shift(int(shift_id))
            if shift:
                shift_st = shift.get("start_time")
                shift_et = shift.get("end_time")
                if shift_st is not None:
                    st = self._time_to_str(shift_st)
                if shift_et is not None:
                    et = self._time_to_str(shift_et)

        if sd and ed:
            try:
                start_str = f"{sd} {st}" if st else sd
                end_str = f"{ed} {et}" if et else ed
                return pd.date_range(start=start_str, end=end_str, freq=freq)
            except Exception:
                pass
        return None

    @staticmethod
    def _time_to_str(val) -> str:
        """Convert shift time (timedelta or str) to 'HH:MM' string."""
        if hasattr(val, "total_seconds"):
            total = int(val.total_seconds())
            return f"{total // 3600:02d}:{(total % 3600) // 60:02d}"
        s = str(val)
        parts = s.split(":")
        if len(parts) >= 2:
            return f"{int(parts[0]):02d}:{int(parts[1]):02d}"
        return s
