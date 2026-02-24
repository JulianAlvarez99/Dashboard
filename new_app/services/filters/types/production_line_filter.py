"""ProductionLineFilter — Auto-discovery wrapper with class attributes."""

from __future__ import annotations

from new_app.services.filters.types.dropdown import DropdownFilter


class ProductionLineFilter(DropdownFilter):
    """Single-select production line (with optional group aliases)."""

    filter_type    = "dropdown"
    param_name     = "line_id"
    options_source = "production_lines"
    default_value  = None
    placeholder    = "Seleccionar línea"
    required       = True
    depends_on     = None
    ui_config      = {"supports_groups": True}
