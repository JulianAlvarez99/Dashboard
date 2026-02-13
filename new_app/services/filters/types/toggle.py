"""ToggleFilter — Boolean on/off switch."""

from __future__ import annotations

from typing import Any, Optional

from new_app.services.filters.base import InputFilter


class ToggleFilter(InputFilter):
    """Simple boolean toggle."""

    def validate(self, value: Any) -> bool:
        if value is None:
            return not self.config.required
        return isinstance(value, bool)

    def get_default(self) -> bool:
        return bool(self.config.default_value) if self.config.default_value is not None else False

    def to_sql_clause(self, value: Any) -> Optional[tuple[str, dict]]:
        return None
