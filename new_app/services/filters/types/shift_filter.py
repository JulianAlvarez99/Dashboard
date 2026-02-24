"""ShiftFilter — Auto-discovery wrapper with class attributes."""

from __future__ import annotations

from new_app.services.filters.types.dropdown import DropdownFilter


class ShiftFilter(DropdownFilter):
    """Shift selection dropdown."""

    filter_type    = "dropdown"
    param_name     = "shift_id"
    options_source = "shifts"
    default_value  = None
    placeholder    = "Todos los turnos"
    required       = False
    depends_on     = None
    ui_config      = {}
