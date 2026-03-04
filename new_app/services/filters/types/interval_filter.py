"""
IntervalFilter — Time-interval granularity selector (static options).

Not a SQL filter — interval is used in Python/BI processing only.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from new_app.services.filters.base import FilterOption, OptionsFilter


class IntervalFilter(OptionsFilter):
    """Time interval granularity dropdown (static options)."""

    filter_type    = "dropdown"
    param_name     = "interval"
    options_source = None
    default_value  = "hour"
    placeholder    = None
    required       = True
    depends_on     = None
    ui_config      = {
        "static_options": [
            {"value": "minute", "label": "Por minuto"},
            {"value": "15min",  "label": "Cada 15 minutos"},
            {"value": "hour",   "label": "Por hora"},
            {"value": "day",    "label": "Por día"},
            {"value": "week",   "label": "Por semana"},
            {"value": "month",  "label": "Por mes"},
        ]
    }

    # ── Frontend contract ────────────────────────────
    pydantic_type = "str"
    js_behavior   = {
        "serialize":  "str",
        "include_if": "always",
        "on_change":  "onIntervalChange",
    }
    js_inline = """\
    onIntervalChange() {
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
        # Interval is used in Python/BI processing, not in SQL WHERE
        return None
