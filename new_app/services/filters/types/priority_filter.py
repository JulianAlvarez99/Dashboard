"""PriorityFilter — Static dropdown for alert/event priority level."""

from __future__ import annotations

from new_app.services.filters.types.dropdown import DropdownFilter


class PriorityFilter(DropdownFilter):
    """
    Single-select dropdown to filter by priority level.

    Options are defined statically via ui_config["static_options"],
    so no MetadataCache lookup is required.

    SQL: ``priority = :priority``
    """

    filter_type    = "dropdown"
    param_name     = "priority"
    options_source = None
    default_value  = None
    placeholder    = "Todas las prioridades"
    required       = False
    depends_on     = None
    ui_config      = {
        "static_options": [
            {"value": "high",   "label": "Alta"},
            {"value": "medium", "label": "Media"},
            {"value": "low",    "label": "Baja"},
        ]
    }
