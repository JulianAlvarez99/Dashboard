"""
ShiftFilter — Shift selection dropdown.

SQL contribution: ``shift_id = :shift_id``
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from new_app.core.cache import metadata_cache
from new_app.services.filters.base import FilterOption, OptionsFilter


class ShiftFilter(OptionsFilter):
    """Shift selection dropdown."""

    filter_type    = "dropdown"
    param_name     = "shift_id"
    options_source = "shifts"
    default_value  = None
    placeholder    = "Todos los turnos"
    required       = False
    depends_on     = None
    ui_config      = {}

    # ── Frontend contract ────────────────────────────
    pydantic_type = "int"
    js_behavior   = {
        "serialize":  "int",
        "include_if": "truthy",
        "on_change":  "onShiftChange",
    }
    js_inline = """\
    onShiftChange() {
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
                value=sid,
                label=d["shift_name"],
                extra={
                    "start_time": str(d["start_time"]),
                    "end_time": str(d["end_time"]),
                },
            )
            for sid, d in metadata_cache.get_shifts().items()
        ]

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
        col = self.config.param_name  # "shift_id"
        return f"{col} = :{col}", {col: value}
