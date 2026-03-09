"""
Only2amFilter — Checkbox toggle para mostrar solo datos de las 2 AM.

SQL contribution: ``HOUR(detected_at) = 2``  (solo cuando está activo)
"""
from __future__ import annotations

from typing import Any, Optional

from new_app.services.filters.base import InputFilter


class OnlyFilter(InputFilter):
    """Checkbox que, al activarse, filtra los datos a únicamente la hora 2 AM."""

    filter_type    = "toggle"
    param_name     = "only_2am"
    options_source = None
    default_value  = False
    placeholder    = None
    required       = False
    depends_on     = None
    ui_config      = {"label": "Solo 2 AM"}

    # ── Frontend contract ─────────────────────────────────────
    pydantic_type = "bool"
    js_behavior   = {
        "serialize":  "bool",
        "include_if": "not_null",
        "on_change":  "",
    }
    js_inline     = None
    js_validation = None

    # ── Validate / Default ────────────────────────────────────

    def validate(self, value: Any) -> bool:
        if value is None:
            return not self.config.required
        return isinstance(value, bool)

    def get_default(self) -> bool:
        return False

    # ── SQL ───────────────────────────────────────────────────

    def to_sql_clause(self, value: Any) -> Optional[tuple[str, dict]]:
        if not value:
            return None
        return "HOUR(detected_at) = :only_2am_hour", {"only_2am_hour": 2}
