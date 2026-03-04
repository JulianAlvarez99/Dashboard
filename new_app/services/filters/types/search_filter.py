"""
SearchFilter — Free-text search input with client-side debounce.

SQL contribution: ``search LIKE :search`` (if used server-side)
"""

from __future__ import annotations

from typing import Any, Optional

from new_app.services.filters.base import InputFilter


class SearchFilter(InputFilter):
    """Free-text search input with client-side debounce."""

    filter_type    = "text"
    param_name     = "search"
    options_source = None
    default_value  = ""
    placeholder    = "Buscar…"
    required       = False
    depends_on     = None
    ui_config      = {"debounce_ms": 300}

    # ── Frontend contract ────────────────────────────────────
    pydantic_type = "str"
    js_behavior   = {
        "serialize":  "str",
        "include_if": "truthy",
        "on_change":  "onSearchChange",
    }
    js_inline = """\
    onSearchChange() {
        if (!this.hasData) return;
        const query = (this.filterStates['search']?.value || '').toLowerCase().trim();

        Object.keys(this.widgetResults).forEach(wid => {
            const wd = this.widgetResults[wid];
            if (!wd || !wd.data || !wd.data.rows) return;

            if (!wd._original_rows) {
                wd._original_rows = wd.data.rows.slice();
            }

            const filtered = !query
                ? wd._original_rows.slice()
                : wd._original_rows.filter(row => {
                    return Object.values(row).some(val =>
                        typeof val === 'string' && val.toLowerCase().includes(query));
                });

            this.widgetResults[wid] = Object.assign({}, wd, {
                data: Object.assign({}, wd.data, { rows: filtered }),
            });
        });
    }"""

    # ── Validate / Default ────────────────────────────────────

    def validate(self, value: Any) -> bool:
        if value is None or value == "":
            return not self.config.required
        if not isinstance(value, str):
            return False
        ui = self.config.ui_config
        mn = ui.get("min_length", 0)
        mx = ui.get("max_length", 1000)
        return mn <= len(value) <= mx

    def get_default(self) -> str:
        return self.config.default_value or ""

    # ── SQL ───────────────────────────────────────────────────

    def to_sql_clause(self, value: Any) -> Optional[tuple[str, dict]]:
        if not value:
            return None
        col = self.config.param_name  # "search"
        return f"{col} LIKE :{col}", {col: f"%{value}%"}
