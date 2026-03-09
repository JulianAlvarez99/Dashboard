"""
BaseFilter — Base class for all filters.

Simple and concrete:
- Each filter has a `filter_type` (dropdown, daterange, toggle, etc.)
- Each filter has a `param_name` (the key used in the frontend state)
- Each filter has a `to_sql_clause(value)` that returns (clause, params) or None
- Each filter has a `get_options()` for filters with selectable options
- Each filter has a `get_default()` for the initial value
- Each filter has a `js_file` property that returns the JS filename

Naming convention:
    DB filter_name:  "ProductionLineFilter"  (CamelCase)
    Python file:     production_line_filter.py
    Python class:    ProductionLineFilter
    JS file:         production_line_filter.js
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class FilterOption:
    """A single selectable option (for dropdowns, multiselect, etc.)."""
    value: Any              # The value sent to the backend
    label: str              # Human-readable text shown in the UI
    extra: Dict = field(default_factory=dict)  # Additional metadata (e.g. is_group, line_ids)


@dataclass
class FilterConfig:
    """
    Runtime configuration for a filter instance.

    Merges the DB row (filter_id, filter_name, display_order, etc.)
    with the class-level attributes (filter_type, param_name, etc.).
    """
    # From DB
    filter_id: int
    filter_name: str        # CamelCase class name, e.g. "ProductionLineFilter"
    description: str
    display_order: int
    additional_filter: Any  # JSON from DB — group definitions, extra config, etc.

    # From class (set by FilterEngine after instantiation)
    filter_type: str = ""
    param_name: str = ""
    required: bool = False
    placeholder: str = ""
    default_value: Any = None
    ui_config: Dict = field(default_factory=dict)


def camel_to_snake(name: str) -> str:
    """
    Convert CamelCase to snake_case.

    Examples:
        ProductionLineFilter → production_line_filter
        DateRangeFilter → date_range_filter
        OnlyFilter → only_filter
    """
    s = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', name)
    s = re.sub(r'([a-z\d])([A-Z])', r'\1_\2', s)
    return s.lower()


class BaseFilter:
    """
    Base class that all filters must extend.

    Subclasses MUST define:
        - filter_type: str     (dropdown, daterange, toggle, etc.)
        - param_name: str      (key in the frontend filter state)
        - to_sql_clause(value) (returns tuple or None)
        - get_default()        (initial value)

    Subclasses MAY override:
        - get_options()        (for filters with selectable options)
        - validate(value)      (input validation)
    """

    # ── Class-level attributes (overridden by each subclass) ────
    filter_type: str = ""           # "dropdown", "daterange", "toggle", etc.
    param_name: str = ""            # "line_id", "daterange", "only_2am", etc.
    required: bool = False
    placeholder: str = ""
    default_value: Any = None
    ui_config: Dict = {}            # Extra UI config (e.g. show_time, label)

    def __init__(self, config: FilterConfig):
        """
        Args:
            config: Merged DB + class configuration.
        """
        self.config = config

    # ── JS file (auto-derived from class name) ──────────────────

    @property
    def js_file(self) -> str:
        """
        JS filename for this filter.

        Derived from the class name:
            ProductionLineFilter → production_line_filter.js
        """
        return camel_to_snake(self.__class__.__name__) + ".js"

    # ── Options (for dropdown-type filters) ─────────────────────

    def get_options(self) -> List[FilterOption]:
        """
        Return the list of selectable options.

        Override in subclasses that have options (dropdowns, multiselect).
        Filters without options (daterange, toggle) return [].
        """
        return []

    # ── Default value ───────────────────────────────────────────

    def get_default(self) -> Any:
        """Return the initial value for this filter."""
        return self.default_value

    # ── Validation ──────────────────────────────────────────────

    def validate(self, value: Any) -> bool:
        """
        Validate user input for this filter.

        Returns True if the value is acceptable.
        """
        if value is None:
            return not self.required
        return True

    # ── SQL clause generation ───────────────────────────────────

    def to_sql_clause(self, value: Any) -> Optional[Tuple[str, Dict]]:
        """
        Convert the user's filter value into a SQL WHERE clause.

        Returns:
            ("clause_string", {param_name: param_value}) or None if no clause.

        Example:
            ("line_id = :line_id", {"line_id": 3})
            ("detected_at BETWEEN :start_dt AND :end_dt", {"start_dt": ..., "end_dt": ...})
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement to_sql_clause()"
        )

    # ── Serialization (for passing to the frontend) ─────────────

    def to_dict(self) -> Dict:
        """
        Serialize this filter for the frontend.

        Returns a dict that the template can render as a filter control.
        """
        options = self.get_options()
        return {
            "filter_id": self.config.filter_id,
            "filter_name": self.config.filter_name,
            "filter_type": self.filter_type,
            "param_name": self.param_name,
            "description": self.config.description,
            "display_order": self.config.display_order,
            "required": self.required,
            "placeholder": self.placeholder,
            "default_value": self.get_default(),
            "ui_config": self.ui_config,
            "js_file": self.js_file,
            "options": [
                {"value": o.value, "label": o.label, "extra": o.extra}
                for o in options
            ],
        }
