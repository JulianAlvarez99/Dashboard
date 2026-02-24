"""AreaFilter — Auto-discovery wrapper with class attributes."""

from __future__ import annotations

from new_app.services.filters.types.multiselect import MultiselectFilter


class AreaFilter(MultiselectFilter):
    """Multi-select area filter (cascades from line_id)."""

    filter_type    = "multiselect"
    param_name     = "area_ids"
    options_source = "areas"
    default_value  = []
    placeholder    = "Todas las áreas"
    required       = False
    depends_on     = "line_id"
    ui_config      = {}
