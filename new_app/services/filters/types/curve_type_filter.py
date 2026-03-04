"""
CurveTypeFilter — Chart curve-type selector (static options).

Not a SQL filter — applied client-side by ChartRenderer.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from new_app.services.filters.base import FilterOption, OptionsFilter


class CurveTypeFilter(OptionsFilter):
    """Chart curve type selector (static options)."""

    filter_type    = "dropdown"
    param_name     = "curve_type"
    options_source = None
    default_value  = "smooth"
    placeholder    = None
    required       = False
    depends_on     = None
    ui_config      = {
        "static_options": [
            {"value": "smooth",  "label": "Suavizado"},
            {"value": "linear",  "label": "Lineal"},
            {"value": "stepped", "label": "Escalonado"},
            {"value": "stacked", "label": "Apilado"},
        ]
    }

    # ── Frontend contract ────────────────────────────
    pydantic_type = "str"
    js_behavior   = {
        "serialize":  "str",
        "include_if": "always",
        "on_change":  "onCurveTypeChange",
    }
    js_inline = """\
    onCurveTypeChange() {
        if (!this.hasData) return;
        this.$nextTick(() => {
            const newCurve = this.filterStates['curve_type']?.value || 'smooth';
            Object.keys(this.widgetResults).forEach(wid => {
                const wd = this.widgetResults[wid];
                if (wd && wd.data) wd.data.curve_type = newCurve;
            });
            ChartRenderer.updateCurveType(this.chartInstances, newCurve);
        });
    }"""

    # ── Options ───────────────────────────────────────────────

    def _load_options(
        self,
        parent_values: Optional[Dict[str, Any]] = None,
    ) -> List[FilterOption]:
        """Return static options defined in ui_config."""
        static = self.config.ui_config.get("static_options", [])
        return [
            FilterOption(value=o["value"], label=o["label"])
            for o in static
        ]

    # ── Validate / Default ────────────────────────────────────

    def validate(self, value: Any) -> bool:
        if value is None or value == "":
            return not self.config.required
        opts = self.get_options()
        return any(str(o.value) == str(value) for o in opts)

    def get_default(self) -> Any:
        return self.config.default_value

    # ── SQL ───────────────────────────────────────────────────

    def to_sql_clause(self, value: Any) -> Optional[tuple[str, dict]]:
        # Curve type is applied client-side, not in SQL
        return None
