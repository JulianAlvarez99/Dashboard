"""ProductFilter — Auto-discovery wrapper with class attributes."""

from __future__ import annotations

from new_app.services.filters.types.multiselect import MultiselectFilter


class ProductFilter(MultiselectFilter):
    """Multi-select product filter."""

    filter_type    = "multiselect"
    param_name     = "product_ids"
    options_source = "products"
    default_value  = []
    placeholder    = "Todos los productos"
    required       = False
    depends_on     = None
    ui_config      = {}
