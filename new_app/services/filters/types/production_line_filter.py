"""
ProductionLineFilter — Single-select production line with optional group aliases.

SQL contribution: ``line_id = :line_id``  (or ``line_id IN :line_ids`` for groups)
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from new_app.core.cache import metadata_cache
from new_app.services.filters.base import FilterOption, OptionsFilter


class ProductionLineFilter(OptionsFilter):
    """Single-select production line (with optional group aliases)."""

    filter_type    = "dropdown"
    param_name     = "line_id"
    options_source = "production_lines"
    default_value  = None
    placeholder    = "Seleccionar línea"
    required       = True
    depends_on     = None
    ui_config      = {"supports_groups": True}

    # ── Frontend contract ────────────────────────────
    pydantic_type = "Any"
    js_behavior   = {
        "serialize":  "line_id",
        "include_if": "truthy",
        "on_change":  "onLineChange",
    }
    js_validation = {"required": True, "required_msg": "Seleccioná una línea de producción"}
    js_inline = """\
    async onLineChange(rawValue) {
        const opt = this._lineOptions.find(o => String(o.value) === String(rawValue));
        if (opt && opt.extra && opt.extra.is_group) {
            this.isMultiLine = true;
            this.selectedLineGroup = opt.extra.line_ids;
            if (this.filterStates['area_ids']) this.filterStates['area_ids'].value = [];
            console.log('[Line] Group selected:', opt.label, '→ lines', opt.extra.line_ids);
        } else if (rawValue) {
            this.isMultiLine = false;
            this.selectedLineGroup = null;
            try {
                const areas = await DashboardAPI.fetchAreas(this.apiBase, rawValue);
                console.log('[Cascade] Areas for line', rawValue, ':', areas.length, 'options');
            } catch (e) {
                console.warn('[Cascade] Failed:', e);
            }
        } else {
            this.isMultiLine = false;
            this.selectedLineGroup = null;
        }
    }"""

    # ── Options ───────────────────────────────────────────────

    def _load_options(
        self,
        parent_values: Optional[Dict[str, Any]] = None,
    ) -> List[FilterOption]:
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

    # ── Validate / Default ────────────────────────────────────

    def validate(self, value: Any) -> bool:
        if value is None or value == "":
            return not self.config.required
        opts = self.get_options()
        return any(
            o.value == value or str(o.value) == str(value)
            for o in opts
        )

    def get_default(self) -> Any:
        return self.config.default_value

    # ── SQL ───────────────────────────────────────────────────

    def to_sql_clause(self, value: Any) -> Optional[tuple[str, dict]]:
        if value is None:
            return None
        col = self.config.param_name  # "line_id"

        # Handle line groups (value = "all" or "group_X")
        opt = next(
            (o for o in self.get_options()
             if o.value == value or str(o.value) == str(value)),
            None,
        )
        if opt and opt.extra and opt.extra.get("is_group"):
            ids = opt.extra["line_ids"]
            return "line_id IN :line_ids", {"line_ids": ids}

        return f"{col} = :{col}", {col: value}
