"""
Product Ranking Processor — top products by production count.

SRP: This module is solely responsible for building the product-ranking
     table API response.
"""

from __future__ import annotations

from typing import Dict, Any, TYPE_CHECKING

from app.services.processors.helpers import empty_widget

if TYPE_CHECKING:
    from app.services.dashboard_data_service import DashboardData
    from app.services.widgets.aggregators import DataAggregator


def process_product_ranking(
    widget_id: int,
    name: str,
    wtype: str,
    data: "DashboardData",
    aggregator: "DataAggregator",
) -> Dict[str, Any]:
    """
    Top products ranked by production count.

    Returns a table-like structure with product name, count, weight,
    and percentage of total production.
    """
    df = data.detections
    if df.empty or "product_name" not in df.columns:
        return empty_widget(widget_id, name, wtype)

    # Consider only output area for production count
    if "area_type" in df.columns:
        output_df = df[df["area_type"] == "output"]
    else:
        output_df = df

    if output_df.empty:
        return empty_widget(widget_id, name, wtype)

    total = len(output_df)

    # Group by product
    grouped = (
        output_df.groupby(["product_name", "product_code", "product_color"])
        .agg(
            count=("product_name", "size"),
            total_weight=("product_weight", "sum"),
        )
        .reset_index()
        .sort_values("count", ascending=False)
    )

    rows = []
    for _, row in grouped.iterrows():
        pct = round((row["count"] / total) * 100, 1) if total > 0 else 0
        rows.append({
            "product_name": row["product_name"],
            "product_code": row["product_code"],
            "product_color": row["product_color"],
            "count": int(row["count"]),
            "total_weight": round(float(row["total_weight"]), 2),
            "percentage": pct,
        })

    columns = [
        {"key": "product_name", "label": "Producto"},
        {"key": "count", "label": "Cantidad"},
        {"key": "total_weight", "label": "Peso (kg)"},
        {"key": "percentage", "label": "% del Total"},
    ]

    return {
        "widget_id": widget_id,
        "widget_name": name,
        "widget_type": wtype,
        "data": {
            "columns": columns,
            "rows": rows,
            "total_production": total,
        },
        "metadata": {
            "widget_category": "table",
            "total_rows": len(rows),
        },
    }
