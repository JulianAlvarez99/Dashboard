"""Chart: Detection distribution by area — bar chart."""

from __future__ import annotations

from new_app.services.widgets.base import BaseWidget, WidgetResult
from new_app.services.widgets.helpers import FALLBACK_PALETTE


class AreaDetectionChart(BaseWidget):

    def process(self) -> WidgetResult:
        df = self.df
        if df.empty or "area_name" not in df.columns:
            return self._empty("chart")

        series = df.groupby("area_name").size().sort_values(ascending=False)

        return self._result(
            "chart",
            {
                "labels": series.index.tolist(),
                "datasets": [
                    {
                        "label": "Detecciones por Área",
                        "data": series.values.tolist(),
                        "backgroundColor": FALLBACK_PALETTE[: len(series)],
                    }
                ],
            },
            category="chart",
            total_points=len(series),
        )
