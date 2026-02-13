"""
DropdownFilter — Single-value selection from cache or static options.

SQL contribution: ``{column} = :param_name``
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from new_app.core.cache import metadata_cache
from new_app.services.filters.base import FilterConfig, FilterOption, OptionsFilter


class DropdownFilter(OptionsFilter):
    """Single-select dropdown fed from MetadataCache or static list."""

    # ── Options ──────────────────────────────────────────────

    def _load_options(
        self,
        parent_values: Optional[Dict[str, Any]] = None,
    ) -> List[FilterOption]:
        # Static options from ui_config
        static = self.config.ui_config.get("static_options")
        if static:
            return [
                FilterOption(value=o["value"], label=o["label"])
                for o in static
            ]

        source = self.config.options_source
        if not source:
            return []

        loader = _LOADERS.get(source)
        if loader is None:
            return []
        return loader(self, parent_values)

    # ── Validate / Default ───────────────────────────────────

    def validate(self, value: Any) -> bool:
        if value is None:
            return not self.config.required
        opts = self.get_options()
        # Support both int and string comparison (group values are strings)
        return any(
            o.value == value or str(o.value) == str(value)
            for o in opts
        )

    def get_default(self) -> Any:
        return self.config.default_value

    # ── SQL ──────────────────────────────────────────────────

    def to_sql_clause(self, value: Any) -> Optional[tuple[str, dict]]:
        if value is None:
            return None
        col = self.config.param_name  # e.g. "line_id", "shift_id"

        # Handle line groups (value = "all" or "group_X")
        if self.config.options_source == "production_lines":
            opt = next(
                (o for o in self.get_options()
                 if o.value == value or str(o.value) == str(value)),
                None,
            )
            if opt and opt.extra and opt.extra.get("is_group"):
                ids = opt.extra["line_ids"]
                return (
                    f"line_id IN :line_ids",
                    {"line_ids": ids},
                )

        return f"{col} = :{col}", {col: value}


# ─────────────────────────────────────────────────────────────
#  OPTION LOADERS  (kept here to avoid circular imports)
# ─────────────────────────────────────────────────────────────

def _load_production_lines(flt: DropdownFilter, _pv) -> List[FilterOption]:
    """Load production lines with optional line-group aliases.

    Scans the ``additional_filter`` column of every cached filter row
    looking for group definitions::

        {"alias": "Fraccionado", "line_ids": [2,3,4]}
        {"groups": [{"alias": "A", "line_ids": [1,2]}, ...]}

    Returns options ordered: *All lines* → groups → individual lines.
    """
    lines = metadata_cache.get_production_lines()
    options: list[FilterOption] = []

    # 1. "Todas las líneas" shortcut when >1 line
    all_ids = list(lines.keys())
    if len(all_ids) > 1:
        options.append(FilterOption(
            value="all",
            label="Todas las líneas",
            extra={"is_group": True, "line_ids": all_ids},
        ))

    # 2. Groups from additional_filter of ANY filter row
    filters = metadata_cache.get_filters()
    for fid, fdata in filters.items():
        af = fdata.get("additional_filter")
        if not af:
            continue
        if isinstance(af, str):
            try:
                af = json.loads(af)
            except (json.JSONDecodeError, TypeError):
                continue
        if not isinstance(af, dict):
            continue

        # Single group: {"alias": "...", "line_ids": [...]}
        if "alias" in af and "line_ids" in af:
            options.append(FilterOption(
                value=f"group_{fid}",
                label=af["alias"],
                extra={"is_group": True, "line_ids": af["line_ids"]},
            ))
        # Multiple groups: {"groups": [{"alias": ..., "line_ids": ...}, ...]}
        elif "groups" in af:
            for idx, grp in enumerate(af["groups"]):
                if "alias" in grp and "line_ids" in grp:
                    options.append(FilterOption(
                        value=f"group_{fid}_{idx}",
                        label=grp["alias"],
                        extra={"is_group": True, "line_ids": grp["line_ids"]},
                    ))

    # 3. Individual lines
    for lid, d in lines.items():
        options.append(FilterOption(
            value=lid,
            label=d["line_name"],
            extra={
                "is_group": False,
                "line_ids": None,
                "line_code": d["line_code"],
                "downtime_threshold": d.get("downtime_threshold"),
            },
        ))

    return options


def _load_shifts(flt: DropdownFilter, _pv) -> List[FilterOption]:
    return [
        FilterOption(
            value=sid,
            label=d["shift_name"],
            extra={"start_time": str(d["start_time"]), "end_time": str(d["end_time"])},
        )
        for sid, d in metadata_cache.get_shifts().items()
    ]


def _load_areas(flt: DropdownFilter, parent_values) -> List[FilterOption]:
    areas = metadata_cache.get_areas()
    if flt.config.depends_on == "line_id" and parent_values:
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


def _load_products(flt: DropdownFilter, _pv) -> List[FilterOption]:
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


# Map options_source strings → loader functions
_LOADERS: Dict[str, Any] = {
    "production_lines": _load_production_lines,
    "shifts": _load_shifts,
    "areas": _load_areas,
    "products": _load_products,
}
