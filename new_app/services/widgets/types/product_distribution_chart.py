"""Chart: Distribution by product — pie chart."""

from __future__ import annotations

from new_app.services.widgets.base import BaseWidget, WidgetResult


class ProductDistributionChart(BaseWidget):

    def process(self) -> WidgetResult:
        df = self.df
        if df.empty or "product_name" not in df.columns:
            return self._empty("chart")

        grouped = (
            df.groupby(["product_name", "product_color"])
            .size()
            .reset_index(name="count")
        )

        return self._result(
            "chart",
            {
                "labels": grouped["product_name"].tolist(),
                "datasets": [
                    {
                        "data": grouped["count"].tolist(),
                        "backgroundColor": grouped["product_color"].tolist(),
                    }
                ],
            },
            category="chart",
            total_points=len(grouped),
        )
