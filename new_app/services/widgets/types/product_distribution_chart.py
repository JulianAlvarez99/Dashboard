"""Chart: Distribution by product — pie chart + summary table."""

from __future__ import annotations

from new_app.services.widgets.base import BaseWidget, WidgetResult


class ProductDistributionChart(BaseWidget):
    required_columns = ["product_name", "product_color", "product_weight"]
    default_config   = {}
    render           = "chart"
    chart_type       = "pie_chart"
    chart_height     = "320px"   # taller to fit more table rows

    def process(self) -> WidgetResult:
        df = self.df
        if df.empty or "product_name" not in df.columns:
            return self._empty("chart")

        # Ensure numeric weight (fallback 0 if missing)
        if "product_weight" in df.columns:
            df = df.copy()
            df["product_weight"] = df["product_weight"].fillna(0).astype(float)
        else:
            df = df.copy()
            df["product_weight"] = 0.0

        grouped = (
            df.groupby(["product_name", "product_color"], sort=False)
            .agg(
                count=("product_name", "size"),
                total_weight=("product_weight", "sum"),
            )
            .reset_index()
            .sort_values("count", ascending=False)
        )

        total = grouped["count"].sum() or 1  # avoid div/0

        table_rows = [
            {
                "label":        row["product_name"],
                "color":        row["product_color"],
                "count":        int(row["count"]),
                "weight_kg":    round(float(row["total_weight"]), 2),
                "pct":          round(float(row["count"]) / total * 100, 1),
            }
            for _, row in grouped.iterrows()
        ]

        return self._result(
            "chart",
            {
                "labels":     grouped["product_name"].tolist(),
                "datasets": [
                    {
                        "data":            grouped["count"].tolist(),
                        "backgroundColor": grouped["product_color"].tolist(),
                    }
                ],
                "table_rows": table_rows,
            },
            category="chart",
            total_points=len(grouped),
        )
