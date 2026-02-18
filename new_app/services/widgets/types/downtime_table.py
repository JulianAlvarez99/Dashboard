"""
Table: Downtime events enriched with failure and incident data.

Iterates downtime DataFrame and looks up the incident → failure
chain from MetadataCache.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from new_app.core.cache import metadata_cache
from new_app.services.widgets.base import BaseWidget, WidgetResult

_COLUMNS = [
    {"key": "start_time", "label": "Inicio"},
    {"key": "end_time", "label": "Fin"},
    {"key": "duration_min", "label": "Duración (min)"},
    {"key": "failure_type", "label": "Tipo de Falla"},
    {"key": "failure_desc", "label": "Descripción Falla"},
    {"key": "incident_code", "label": "Código Incidente"},
    {"key": "incident_desc", "label": "Incidente"},
    {"key": "line_name", "label": "Línea"},
]


class DowntimeTable(BaseWidget):

    def process(self) -> WidgetResult:
        dt_df = self.downtime_df

        if dt_df.empty:
            return self._result(
                "table",
                {"columns": _COLUMNS, "rows": []},
                category="table",
                total_rows=0,
            )

        failures = metadata_cache.get_failures()
        incidents = metadata_cache.get_incidents()

        rows: List[Dict[str, Any]] = []
        for _, row in dt_df.iterrows():
            reason_code = row.get("reason_code")

            incident = incidents.get(int(reason_code)) if reason_code else None
            incident_code = incident["incident_code"] if incident else ""
            incident_desc = incident["description"] if incident else ""

            failure_id = incident["failure_id"] if incident else None
            failure = failures.get(failure_id) if failure_id else None
            failure_type = failure["type_failure"] if failure else ""
            failure_desc = failure["description"] if failure else ""

            rows.append({
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
            })

        return self._result(
            "table",
            {"columns": _COLUMNS, "rows": rows},
            category="table",
            total_rows=len(rows),
        )
