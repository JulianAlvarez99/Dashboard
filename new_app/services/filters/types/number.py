"""NumberFilter — Numeric input with min/max bounds."""

from __future__ import annotations

from typing import Any, Optional, Union

from new_app.services.filters.base import InputFilter


class NumberFilter(InputFilter):
    """Numeric input filter with validation bounds."""

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

    def to_sql_clause(self, value: Any) -> Optional[tuple[str, dict]]:
        # Number filters are usually non-SQL (e.g. downtime threshold is
        # applied in Python processing, not SQL WHERE).
        return None
