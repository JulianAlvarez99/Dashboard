"""ShowDowntimeFilter — Auto-discovery wrapper with class attributes."""

from __future__ import annotations

from new_app.services.filters.types.toggle import ToggleFilter


class ShowDowntimeFilter(ToggleFilter):
    """Boolean toggle to show/hide downtime overlay."""

    filter_type    = "toggle"
    param_name     = "show_downtime"
    options_source = None
    default_value  = True
    placeholder    = None
    required       = False
    depends_on     = None
    ui_config      = {"label": "Mostrar paradas"}
