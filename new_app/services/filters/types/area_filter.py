"""
AreaFilter — Multi-select area filter (cascades from line_id).

SQL contribution: ``area_ids IN :area_ids``
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from new_app.core.cache import metadata_cache
from new_app.services.filters.base import FilterOption, OptionsFilter


class AreaFilter(OptionsFilter):
    """Multi-select area filter (cascades from line_id)."""

    filter_type    = "multiselect"
    param_name     = "area_ids"
    options_source = "areas"
    default_value  = []
    placeholder    = "Todas las áreas"
    required       = False
    depends_on     = "line_id"
    ui_config      = {}

    # ── Frontend contract ────────────────────────────
    pydantic_type = "List[int]"
    js_behavior   = {
        "serialize":  "array_int",
        "include_if": "array_not_empty",
        "on_change":  "",
    }
    js_inline     = None

    # ── Options ───────────────────────────────────────────────

    def _load_options(
        self,
        parent_values: Optional[Dict[str, Any]] = None,
    ) -> List[FilterOption]:
        areas = metadata_cache.get_areas()
        if self.config.depends_on == "line_id" and parent_values:
            lid = parent_values.get("line_id")
            if lid is not None:
                areas = {k: v for k, v in areas.items() if v["line_id"] == lid}
        return [
            FilterOption(
                value=aid,
                label=d["area_name"],
                extra={"area_type": d["area_type"], "line_id": d["line_id"]},
            )
            for aid, d in areas.items()
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
        col = self.config.param_name  # "area_ids"
        return f"{col} IN :{col}", {col: value}
