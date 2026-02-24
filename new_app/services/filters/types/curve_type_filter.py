"""CurveTypeFilter — Auto-discovery wrapper with class attributes."""

from __future__ import annotations

from new_app.services.filters.types.dropdown import DropdownFilter


class CurveTypeFilter(DropdownFilter):
    """Chart curve type selector (static options)."""

    filter_type    = "dropdown"
    param_name     = "curve_type"
    options_source = None
    default_value  = "smooth"
    placeholder    = None
    required       = False
    depends_on     = None
    ui_config      = {
        "static_options": [
            {"value": "smooth",  "label": "Suavizado"},
            {"value": "linear",  "label": "Lineal"},
            {"value": "stepped", "label": "Escalonado"},
            {"value": "stacked", "label": "Apilado"},
        ]
    }
