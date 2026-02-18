"""Ranking: Top products by production count."""

from __future__ import annotations

from typing import Any, Dict, List

from new_app.services.widgets.base import BaseWidget, WidgetResult


class ProductRanking(BaseWidget):

    def process(self) -> WidgetResult:
        df = self.df
        if df.empty or "product_name" not in df.columns:
            return self._empty("ranking")

        # Consider only output area for production count
        if "area_type" in df.columns:
            output_df = df[df["area_type"] == "output"]
        else:
            output_df = df

        if output_df.empty:
            return self._empty("ranking")

        total = len(output_df)

        cols_for_group = ["product_name"]
        if "product_code" in output_df.columns:
            cols_for_group.append("product_code")
        if "product_color" in output_df.columns:
            cols_for_group.append("product_color")

        agg_dict: Dict[str, Any] = {"product_name": ("product_name", "size")}
        if "product_weight" in output_df.columns:
            agg_dict["total_weight"] = ("product_weight", "sum")

        grouped = (
            output_df.groupby(cols_for_group)
            .agg(count=("product_name", "size"),
                 total_weight=("product_weight", "sum") if "product_weight" in output_df.columns else ("product_name", "size"))
            .reset_index()
            .sort_values("count", ascending=False)
        )

        rows: List[Dict[str, Any]] = []
        for _, row in grouped.iterrows():
            pct = round((row["count"] / total) * 100, 1) if total > 0 else 0
            rows.append({
                "product_name": row["product_name"],
                "product_code": row.get("product_code", ""),
                "product_color": row.get("product_color", "#999"),
                "count": int(row["count"]),
                "total_weight": round(float(row.get("total_weight", 0)), 2),
                "percentage": pct,
            })

        columns = [
            {"key": "product_name", "label": "Producto"},
            {"key": "count", "label": "Cantidad"},
            {"key": "total_weight", "label": "Peso (kg)"},
            {"key": "percentage", "label": "% del Total"},
        ]

        return self._result(
            "ranking",
            {"columns": columns, "rows": rows, "total_production": total},
            category="table",
            total_rows=len(rows),
        )
