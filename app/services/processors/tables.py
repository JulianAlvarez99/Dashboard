"""
Table Processors — downtime table (and future table widgets).

Each processor receives (widget_id, name, wtype, data)
and returns a Dict[str, Any] ready for the API response.
"""

from __future__ import annotations

from typing import Dict, Any, TYPE_CHECKING

import pandas as pd

from app.core.cache import metadata_cache

if TYPE_CHECKING:
    from app.services.dashboard_data_service import DashboardData


# ─── Column definitions (reusable) ──────────────────────────────────

_DOWNTIME_COLUMNS = [
    {"key": "start_time", "label": "Inicio"},
    {"key": "end_time", "label": "Fin"},
    {"key": "duration_min", "label": "Duración (min)"},
    {"key": "failure_type", "label": "Tipo de Falla"},
    {"key": "failure_desc", "label": "Descripción Falla"},
    {"key": "incident_code", "label": "Código Incidente"},
    {"key": "incident_desc", "label": "Incidente"},
    {"key": "line_name", "label": "Línea"},
]


# ─── Downtime Table ─────────────────────────────────────────────────

def process_downtime_table(
    widget_id: int, name: str, wtype: str, data: "DashboardData"
) -> Dict[str, Any]:
    """Downtime events table, enriched with failure and incident data."""
    downtime_df = data.downtime

    if downtime_df.empty:
        return {
            "widget_id": widget_id,
            "widget_name": name,
            "widget_type": wtype,
            "data": {"columns": _DOWNTIME_COLUMNS, "rows": []},
            "metadata": {"widget_category": "table", "total_rows": 0},
        }

    failures = metadata_cache.get_failures()
    incidents = metadata_cache.get_incidents()

    rows = []
    for _, row in downtime_df.iterrows():
        reason_code = row.get("reason_code")

        # reason_code → incident_id: look up incident first
        incident = incidents.get(int(reason_code)) if reason_code else None
        incident_code = incident["incident_code"] if incident else ""
        incident_desc = incident["description"] if incident else ""

        # incident.failure_id → failure
        failure_id = incident["failure_id"] if incident else None
        failure = failures.get(failure_id) if failure_id else None
        failure_type = failure["type_failure"] if failure else ""
        failure_desc = failure["description"] if failure else ""

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
                "failure_type": failure_type,
                "failure_desc": failure_desc,
                "incident_code": incident_code,
                "incident_desc": incident_desc,
                "line_name": row.get("line_name", ""),
            }
        )

    return {
        "widget_id": widget_id,
        "widget_name": name,
        "widget_type": wtype,
        "data": {"columns": _DOWNTIME_COLUMNS, "rows": rows},
        "metadata": {"widget_category": "table", "total_rows": len(rows)},
    }
