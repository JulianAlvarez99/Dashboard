"""
ShowDowntimeFilter — Boolean toggle to show/hide downtime overlay.

Not a SQL filter — controls chart annotation rendering client-side.
"""

from __future__ import annotations

from typing import Any, Optional

from new_app.services.filters.base import InputFilter


class ShowDowntimeFilter(InputFilter):
    """Boolean toggle to show/hide downtime overlay."""

    filter_type    = "toggle"
    param_name     = "show_downtime"
    options_source = None
    default_value  = True
    placeholder    = None
    required       = False
    depends_on     = None
    ui_config      = {"label": "Mostrar paradas"}

    # ── Frontend contract ────────────────────────────
    pydantic_type = "bool"
    js_behavior   = {
        "serialize":  "bool",
        "include_if": "not_null",
        "on_change":  "onShowDowntimeChange",
    }
    js_inline = """\
    onShowDowntimeChange() {
        if (!this.hasData) return;
        const show = !!(this.filterStates['show_downtime']?.value);
        Object.keys(this.widgetResults).forEach(wid => {
            const wd = this.widgetResults[wid];
            if (wd && wd.data) wd.data.show_downtime = show;
        });
        ChartRenderer.updateDowntimeAnnotations(this.chartInstances, this._rawDowntime || [], show);
    }"""

    # ── Validate / Default ────────────────────────────────────

    def validate(self, value: Any) -> bool:
        if value is None:
            return not self.config.required
        return isinstance(value, bool)

    def get_default(self) -> bool:
        return bool(self.config.default_value) if self.config.default_value is not None else False

    # ── SQL ───────────────────────────────────────────────────

    def to_sql_clause(self, value: Any) -> Optional[tuple[str, dict]]:
        # Toggle controls chart rendering, not SQL filtering
        return None
