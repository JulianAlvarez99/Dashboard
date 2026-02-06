"""
Table Processors — downtime table (and future table widgets).

Each processor receives (widget_id, name, wtype, data)
and returns a Dict[str, Any] ready for the API response.
"""

from __future__ import annotations

from typing import Dict, Any, TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from app.services.dashboard_data_service import DashboardData


# ─── Column definitions (reusable) ──────────────────────────────────

_DOWNTIME_COLUMNS = [
    {"key": "start_time", "label": "Inicio"},
    {"key": "end_time", "label": "Fin"},
    {"key": "duration_min", "label": "Duración (min)"},
    {"key": "reason", "label": "Motivo"},
    {"key": "line_name", "label": "Línea"},
    {"key": "is_manual", "label": "Tipo"},
]


# ─── Downtime Table ─────────────────────────────────────────────────

def process_downtime_table(
    widget_id: int, name: str, wtype: str, data: DashboardData
) -> Dict[str, Any]:
    """Downtime events table."""
    downtime_df = data.downtime

    if downtime_df.empty:
        return {
            "widget_id": widget_id,
            "widget_name": name,
            "widget_type": wtype,
            "data": {"columns": _DOWNTIME_COLUMNS, "rows": []},
            "metadata": {"widget_category": "table", "total_rows": 0},
        }

    rows = []
    for _, row in downtime_df.iterrows():
        rows.append(
            {
                "start_time": (
                    row["start_time"].strftime("%Y-%m-%d %H:%M")
                    if pd.notna(row.get("start_time"))
                    else ""
                ),
                "end_time": (
                    row["end_time"].strftime("%Y-%m-%d %H:%M")
                    if pd.notna(row.get("end_time"))
                    else ""
                ),
                "duration_min": round(row.get("duration", 0) / 60.0, 1),
                "reason": row.get("reason", "Sin motivo") or "Sin motivo",
                "line_name": row.get("line_name", ""),
                "is_manual": "Manual" if row.get("is_manual", 0) else "Automática",
            }
        )

    return {
        "widget_id": widget_id,
        "widget_name": name,
        "widget_type": wtype,
        "data": {"columns": _DOWNTIME_COLUMNS, "rows": rows},
        "metadata": {"widget_category": "table", "total_rows": len(rows)},
    }
