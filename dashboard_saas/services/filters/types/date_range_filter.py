"""
DateRangeFilter — Selector de rango de fecha y hora.

Genera los campos: start_date, end_date, start_time, end_time.
SQL contribution: ``detected_at BETWEEN :start_dt AND :end_dt``

Validación:
    - start_date no puede ser posterior a end_date
    - Si start_date == end_date, start_time no puede ser posterior a end_time
    - Ambas fechas son obligatorias (required = True)

Este filtro NO aporta tablas (get_target_tables devuelve []).
Solo contribuye con una cláusula WHERE sobre la columna `detected_at`.
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from dashboard_saas.services.filters.base import BaseFilter, FilterOption

logger = logging.getLogger(__name__)


class DateRangeFilter(BaseFilter):
    """Filtro de rango de fecha y hora con validación de coherencia."""

    # ── Atributos de clase (contrato con BaseFilter) ──────────────
    filter_type = "daterange"
    param_name = "daterange"
    required = True
    placeholder = ""
    default_value = None        # Se calcula dinámicamente en get_default()
    ui_config = {
        "show_time": True,
        "default_start_time": "00:00",
        "default_end_time": "23:59",
    }

    # ── Options ───────────────────────────────────────────────────
    # El filtro de fechas no tiene opciones seleccionables (no es un dropdown).

    def get_options(self) -> List[FilterOption]:
        """DateRange no tiene opciones desplegables, retorna lista vacía."""
        return []

    # ── Default ───────────────────────────────────────────────────

    def get_default(self) -> Dict[str, str]:
        """
        Valor por defecto: Rango de 1 día hacia atrás (ayer → hoy).
        
        Devuelve un diccionario con las 4 claves que el frontend espera:
        start_date, end_date, start_time, end_time.
        """
        end = date.today()
        start = end - timedelta(days=1)
        return {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "start_time": self.ui_config.get("default_start_time", "00:00"),
            "end_time": self.ui_config.get("default_end_time", "23:59"),
        }

    # ── Validación ────────────────────────────────────────────────

    def validate(self, value: Any) -> bool:
        """
        Validación estricta de coherencia en fechas y horarios.

        Reglas:
        1. Si value es None/vacío y el filtro es required → False
        2. value debe ser un dict con al menos {start_date, end_date}
        3. start_date no puede ser posterior a end_date
        4. Si start_date == end_date, start_time no puede ser posterior a end_time
        """
        # Caso nulo
        if value is None or value == "" or value == {}:
            return not self.required

        # Debe ser un diccionario
        if not isinstance(value, dict):
            return False

        # Claves obligatorias
        if "start_date" not in value or "end_date" not in value:
            return False

        try:
            # Parsear fechas ISO (YYYY-MM-DD)
            s = date.fromisoformat(value["start_date"])
            e = date.fromisoformat(value["end_date"])

            # Regla 3: start_date <= end_date
            if s > e:
                return False

            # Regla 4: Si es el mismo día, validar horarios
            if s == e:
                st = value.get("start_time", "00:00")
                et = value.get("end_time", "23:59")
                if st > et:
                    return False

            return True

        except (ValueError, TypeError):
            return False

    # ── Resolución de Tablas ──────────────────────────────────────

    def get_target_tables(self, value: Any) -> List[str]:
        """
        El filtro de fechas NO aporta tablas. Solo genera una cláusula WHERE.
        La responsabilidad de decidir la tabla recae en el filtro de línea.
        """
        return []

    # ── Parsing interno ──────────────────────────────────────────

    def _parse_datetimes(self, value: Dict[str, str]) -> Dict[str, datetime]:
        """
        Convierte los strings crudos del frontend a objetos datetime de Python.
        
        Ejemplo:
            {"start_date": "2024-01-15", "end_date": "2024-01-16", 
             "start_time": "08:00", "end_time": "23:59"}
            →
            {"start_datetime": datetime(2024, 1, 15, 8, 0),
             "end_datetime":   datetime(2024, 1, 16, 23, 59)}
        """
        sd = date.fromisoformat(value["start_date"])
        ed = date.fromisoformat(value["end_date"])

        # Parsear hora (con fallback a medianoche / fin del día)
        sh, sm = map(int, value.get("start_time", "00:00").split(":"))
        eh, em = map(int, value.get("end_time", "23:59").split(":"))

        return {
            "start_datetime": datetime(sd.year, sd.month, sd.day, sh, sm),
            "end_datetime": datetime(ed.year, ed.month, ed.day, eh, em),
        }

    # ── SQL Clause ───────────────────────────────────────────────

    def to_sql_clause(self, value: Any) -> Optional[Tuple[str, Dict]]:
        """
        Genera la cláusula SQL para filtrar por rango de fecha/hora.

        Resultado:
            ("detected_at BETWEEN :start_dt AND :end_dt", 
             {"start_dt": datetime(...), "end_dt": datetime(...)})
        """
        # Si el valor no es válido, no aportar cláusula
        if not self.validate(value):
            return None

        dts = self._parse_datetimes(value)
        return (
            "detected_at BETWEEN :start_dt AND :end_dt",
            {
                "start_dt": dts["start_datetime"],
                "end_dt": dts["end_datetime"],
            },
        )
