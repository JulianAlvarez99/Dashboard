"""SearchFilter — Auto-discovery wrapper with class attributes."""

from __future__ import annotations

from new_app.services.filters.types.text import TextFilter


class SearchFilter(TextFilter):
    """Free-text search input with client-side debounce."""

    filter_type    = "text"
    param_name     = "search"
    options_source = None
    default_value  = ""
    placeholder    = "Buscar…"
    required       = False
    depends_on     = None
    ui_config      = {"debounce_ms": 300}
