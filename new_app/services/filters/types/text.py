"""TextFilter — Free-text input / search box."""

from __future__ import annotations

from typing import Any, Optional

from new_app.services.filters.base import InputFilter


class TextFilter(InputFilter):
    """Free-text input with optional length constraints."""

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

    def to_sql_clause(self, value: Any) -> Optional[tuple[str, dict]]:
        if not value:
            return None
        col = self.config.param_name
        return f"{col} LIKE :{col}", {col: f"%{value}%"}
