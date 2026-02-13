"""
MultiselectFilter — Multi-value selection (reuses DropdownFilter loaders).

SQL contribution: ``{column} IN :param_name``
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from new_app.services.filters.base import FilterOption
from new_app.services.filters.types.dropdown import DropdownFilter


class MultiselectFilter(DropdownFilter):
    """Multi-select variant — same option loading, list validation."""

    def validate(self, value: Any) -> bool:
        if value is None or value == []:
            return not self.config.required
        if not isinstance(value, list):
            return False
        opts = self.get_options()
        valid = {o.value for o in opts}
        return all(v in valid for v in value)

    def get_default(self) -> List[Any]:
        d = self.config.default_value
        if d is None:
            return []
        return d if isinstance(d, list) else [d]

    def to_sql_clause(self, value: Any) -> Optional[tuple[str, dict]]:
        if not value:
            return None
        col = self.config.param_name
        return f"{col} IN :{col}", {col: value}
