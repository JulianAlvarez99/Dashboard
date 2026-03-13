"""
ShiftFilter — Dropdown para seleccionar turno.

Filtra los datos del dashboard usando el rango horario del turno asignado
(ej: 06:00 a 14:00, o 22:00 a 06:00 para turnos nocturnos).
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from dashboard_saas.core.cache import metadata_cache
from dashboard_saas.services.filters.base import BaseFilter, FilterOption

logger = logging.getLogger(__name__)


class ShiftFilter(BaseFilter):
    """
    Filtro para seleccionar turno. 
    Se traduce a una condición SQL en el campo `detected_at`.
    """

    filter_type = "dropdown"
    param_name = "shift_id"
    required = False
    placeholder = ""
    default_value = "all"
    ui_config = {}

    def get_options(self) -> List[FilterOption]:
        """Extrae la lista de turnos de la DB (vía metadata_cache)."""
        options: List[FilterOption] = []
        shifts = metadata_cache.get_shifts()

        # Opción para no filtrar por turno
        options.append(FilterOption(
            value="all",
            label="Todos los turnos",
            extra={"is_group": True}
        ))

        if not shifts:
            return options

        for shift_id, data in shifts.items():
            # Descartar turnos inactivos si la propiedad existe
            if data.get("shift_status") == 0 or data.get("shift_status") is False:
                continue

            options.append(FilterOption(
                value=shift_id,
                label=data.get("shift_name", f"Turno {shift_id}"),
                extra={
                    "start_time": str(data.get("start_time", "00:00:00")),
                    "end_time": str(data.get("end_time", "23:59:59")),
                    "is_overnight": bool(data.get("is_overnight", False))
                }
            ))

        return options


    def validate(self, value: Any) -> bool:
        """Valida si el id del turno seleccionado es válido."""
        if value is None or value == "":
            return not self.required

        # "all" siempre es válido
        if str(value) == "all":
            return True

        opts = self.get_options()
        return any(
            str(o.value) == str(value)
            for o in opts
        )

    def to_sql_clause(self, value: Any) -> Optional[Tuple[str, Dict]]:
        """Construye la cláusula correspondiente usando TIME(detected_at)."""
        if value is None or value == "" or str(value) == "all":
            return None

        try:
            shift_id = int(value)
        except ValueError:
            return None

        shift = metadata_cache.get_shift(shift_id)
        if not shift:
            logger.warning("Turno %s no encontrado, ignorando filtro", shift_id)
            return None

        start_time = str(shift.get("start_time"))
        end_time = str(shift.get("end_time"))
        is_overnight = bool(shift.get("is_overnight", False))

        # Ajuste de cláusula SQL
        if is_overnight:
            clause = "(TIME(detected_at) >= :shift_start OR TIME(detected_at) <= :shift_end)"
        else:
            clause = "(TIME(detected_at) >= :shift_start AND TIME(detected_at) <= :shift_end)"

        return (
            clause,
            {
                "shift_start": start_time,
                "shift_end": end_time
            }
        )

    def get_default(self) -> Any:
        """Devuelve el valor por defecto para el filtro de turnos."""
        return self.default_value