"""
ProductFilter — Multi-select product filter.

SQL contribution: ``product_ids IN :product_ids``
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from new_app.core.cache import metadata_cache
from new_app.services.filters.base import FilterOption, OptionsFilter


class ProductFilter(OptionsFilter):
    """Multi-select product filter."""

    filter_type    = "multiselect"
    param_name     = "product_ids"
    options_source = "products"
    default_value  = []
    placeholder    = "Todos los productos"
    required       = False
    depends_on     = None
    ui_config      = {}

    # ── Frontend contract ────────────────────────────
    pydantic_type = "List[int]"
    js_behavior   = {
        "serialize":  "array_int",
        "include_if": "array_not_empty",
        "on_change":  "onProductIdsChange",
    }
    js_inline = """\
    onProductIdsChange() {
        if (!this.hasData) return;
        if (this._rawData && this._rawData.length > 0) {
            DashboardOrchestrator.recomputeFromRaw(this);
        } else {
            this._debouncedApply();
        }
    }"""

    # ── Options ───────────────────────────────────────────────

    def _load_options(
        self,
        parent_values: Optional[Dict[str, Any]] = None,
    ) -> List[FilterOption]:
        return [
            FilterOption(
                value=pid,
                label=d["product_name"],
                extra={
                    "product_code": d["product_code"],
                    "product_weight": float(d["product_weight"]),
                    "product_color": d["product_color"],
                },
            )
            for pid, d in metadata_cache.get_products().items()
        ]

    # ── Validate / Default ────────────────────────────────────

    def validate(self, value: Any) -> bool:
        if value is None or value == []:
            return not self.config.required
        if not isinstance(value, list):
            return False
        opts = self.get_options()
        valid = {o.value for o in opts}
        return all(v in valid for v in value)

    def get_default(self) -> List[Any]:
        d = self.config.default_value
        if d is None:
            return []
        return d if isinstance(d, list) else [d]

    # ── SQL ───────────────────────────────────────────────────

    def to_sql_clause(self, value: Any) -> Optional[tuple[str, dict]]:
        if not value:
            return None
        col = self.config.param_name  # "product_ids"
        return f"{col} IN :{col}", {col: value}
