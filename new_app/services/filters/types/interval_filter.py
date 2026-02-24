"""IntervalFilter — Auto-discovery wrapper with class attributes."""

from __future__ import annotations

from new_app.services.filters.types.dropdown import DropdownFilter


class IntervalFilter(DropdownFilter):
    """Time interval granularity dropdown (static options)."""

    filter_type    = "dropdown"
    param_name     = "interval"
    options_source = None
    default_value  = "hour"
    placeholder    = None
    required       = True
    depends_on     = None
    ui_config      = {
        "static_options": [
            {"value": "minute", "label": "Por minuto"},
            {"value": "15min",  "label": "Cada 15 minutos"},
            {"value": "hour",   "label": "Por hora"},
            {"value": "day",    "label": "Por día"},
            {"value": "week",   "label": "Por semana"},
            {"value": "month",  "label": "Por mes"},
        ]
    }
