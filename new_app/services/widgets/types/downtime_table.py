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
    {"key": "tipo",         "label": "Tipo"},
    {"key": "start_time",   "label": "Inicio"},
    {"key": "end_time",     "label": "Fin"},
    {"key": "duration_min", "label": "Duración (min)"},
    {"key": "failure_type", "label": "Tipo de Falla"},
    {"key": "failure_desc", "label": "Descripción Falla"},
    {"key": "incident_code","label": "Cód. Incidente"},
    {"key": "incident_desc","label": "Incidente"},
    {"key": "line_name",    "label": "Línea"},
    {"key": "source_badge", "label": "Origen"},
]


class DowntimeTable(BaseWidget):
    required_columns = []
    default_config   = {}

    # ── Render ──────────────────────────────────────────────
    render       = "table"
    chart_type   = ""
    chart_height = "250px"

    # ── Layout ──────────────────────────────────────────────
    tab          = "produccion"
    col_span     = 3
    row_span     = 2
    order        = 14
    downtime_only = True

    # ── JS ──────────────────────────────────────────────────
    js_inline = None

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
            source      = row.get("source", "db")
            is_manual   = bool(row.get("is_manual", False))

            # Intentar cross-reference solo para paradas DB con motivo
            incident = None
            if source == "db" and reason_code and pd.notna(reason_code):
                try:
                    incident = incidents.get(int(reason_code))
                except (ValueError, TypeError):
                    incident = None
            incident_code = incident["incident_code"] if incident else ""
            incident_desc = incident["description"] if incident else ""

            failure_id = incident["failure_id"] if incident else None
            failure = failures.get(failure_id) if failure_id else None
            failure_type = failure["type_failure"] if failure else ""
            failure_desc = failure["description"] if failure else ""

            # Determinar tipo visual y badge
            if source == "db" and incident:
                tipo         = "Registrada"
                source_badge = "db_confirmed"
            elif source == "db":
                tipo         = "Registrada"
                source_badge = "db_unconfirmed"
            else:
                tipo         = "Calculada"
                source_badge = "calculated"

            rows.append({
                "tipo":         tipo,
                "start_time": (
                    row["start_time"].strftime("%d-%m-%Y %H:%M")
                    if pd.notna(row.get("start_time"))
                    else ""
                ),
                "end_time": (
                    row["end_time"].strftime("%d-%m-%Y %H:%M")
                    if pd.notna(row.get("end_time"))
                    else ""
                ),
                "duration_min": round(row.get("duration", 0) / 60.0, 1),
                "failure_type": failure_type,
                "failure_desc": failure_desc,
                "incident_code": incident_code,
                "incident_desc": incident_desc,
                "line_name":    row.get("line_name", ""),
                "source":       source,
                "source_badge": source_badge,
                "is_manual":    is_manual,
            })

        return self._result(
            "table",
            {"columns": _COLUMNS, "rows": rows},
            category="table",
            total_rows=len(rows),
        )
