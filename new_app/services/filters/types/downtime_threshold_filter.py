"""
DowntimeThresholdFilter — Numeric downtime threshold (seconds).

Applied in Python post-processing, not in SQL WHERE.
"""

from __future__ import annotations

from typing import Any, Optional, Union

from new_app.services.filters.base import InputFilter


class DowntimeThresholdFilter(InputFilter):
    """Numeric downtime threshold (seconds) — applied in Python, not SQL."""

    filter_type    = "number"
    param_name     = "downtime_threshold"
    options_source = None
    default_value  = 10
    placeholder    = "Segundos"
    required       = False
    depends_on     = "line_id"
    ui_config      = {"min": 0, "step": 10, "unit": "s"}

    # ── Frontend contract ────────────────────────────
    pydantic_type = "int"
    js_behavior   = {
        "serialize":  "int",
        "include_if": "not_null",
        "on_change":  "",
    }
    js_inline     = None

    # ── Validate / Default ────────────────────────────────────

    def validate(self, value: Any) -> bool:
        if value is None:
            return not self.config.required
        try:
            v = float(value)
        except (ValueError, TypeError):
            return False
        ui = self.config.ui_config
        lo = ui.get("min")
        hi = ui.get("max")
        if lo is not None and v < lo:
            return False
        if hi is not None and v > hi:
            return False
        return True

    def get_default(self) -> Union[int, float]:
        return self.config.default_value if self.config.default_value is not None else 0

    # ── SQL ───────────────────────────────────────────────────

    def to_sql_clause(self, value: Any) -> Optional[tuple[str, dict]]:
        # Threshold is applied in Python processing, not in SQL WHERE
        return None
