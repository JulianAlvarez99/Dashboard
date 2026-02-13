"""
Base filter classes and dataclasses — Etapa 2 Foundation.

Defines the contract every filter must follow:
  - ``FilterOption``: single option for dropdowns/multiselects.
  - ``FilterConfig``: merged config from DB + FILTER_REGISTRY.
  - ``BaseFilter``: abstract base with validate / get_options / to_sql_clause.
  - ``OptionsFilter``: base for dropdown/multiselect (loads from cache).
  - ``InputFilter``: base for text/number/daterange/toggle (no options).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ─────────────────────────────────────────────────────────────
#  DATA CLASSES
# ─────────────────────────────────────────────────────────────

@dataclass(slots=True)
class FilterOption:
    """Single selectable option for dropdown / multiselect filters."""
    value: Any
    label: str
    extra: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        out = {"value": self.value, "label": self.label}
        if self.extra:
            out["extra"] = self.extra
        return out


@dataclass
class FilterConfig:
    """
    Merged configuration for one filter instance.

    Built by combining the DB row from ``filter`` table with the
    matching entry in ``FILTER_REGISTRY`` (keyed by class_name).
    """
    filter_id: int
    class_name: str          # e.g. "DateRangeFilter"  (= filter.filter_name)
    filter_type: str         # "daterange" | "dropdown" | "multiselect" | ...
    param_name: str          # HTTP param name ("line_id", "daterange", …)
    display_order: int = 0
    description: str = ""
    placeholder: Optional[str] = None
    default_value: Any = None
    required: bool = False
    options_source: Optional[str] = None
    depends_on: Optional[str] = None
    ui_config: Dict[str, Any] = field(default_factory=dict)

    # ── Serialization ──

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filter_id": self.filter_id,
            "class_name": self.class_name,
            "param_name": self.param_name,
            "filter_type": self.filter_type,
            "display_order": self.display_order,
            "description": self.description,
            "placeholder": self.placeholder,
            "default_value": self.default_value,
            "required": self.required,
            "options_source": self.options_source,
            "depends_on": self.depends_on,
            "ui_config": self.ui_config,
        }


# ─────────────────────────────────────────────────────────────
#  ABSTRACT BASES
# ─────────────────────────────────────────────────────────────

class BaseFilter(ABC):
    """
    Abstract base for every filter type.

    Subclasses **must** implement:
      - ``validate(value)``  → bool
      - ``get_default()``    → Any

    May override:
      - ``get_options(parent_values)``  → list[FilterOption]
      - ``to_sql_clause(value)``        → tuple[str, dict] | None
    """

    def __init__(self, config: FilterConfig) -> None:
        self.config = config

    @abstractmethod
    def validate(self, value: Any) -> bool:
        """Return ``True`` if *value* is acceptable for this filter."""

    @abstractmethod
    def get_default(self) -> Any:
        """Return the default value to use when none is provided."""

    def get_options(
        self,
        parent_values: Optional[Dict[str, Any]] = None,
    ) -> List[FilterOption]:
        """Override in option-based filters."""
        return []

    def to_sql_clause(self, value: Any) -> Optional[tuple[str, dict]]:
        """
        Return a ``(sql_fragment, params_dict)`` tuple, or ``None``
        if this filter does not contribute to the WHERE clause.

        Used by the Query Builder (Etapa 3).
        """
        return None

    def to_dict(self, parent_values: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Full serialization including resolved options."""
        out = self.config.to_dict()
        opts = self.get_options(parent_values)
        out["options"] = [o.to_dict() for o in opts]
        out["default_value"] = self.get_default()
        return out


# ─────────────────────────────────────────────────────────────
#  CONVENIENCE BASES
# ─────────────────────────────────────────────────────────────

class OptionsFilter(BaseFilter):
    """
    Base for filters backed by a list of selectable options
    (dropdown, multiselect).  Options are resolved from the
    MetadataCache via ``_load_options``.
    """

    def __init__(self, config: FilterConfig) -> None:
        super().__init__(config)
        self._cached_options: Optional[List[FilterOption]] = None

    @abstractmethod
    def _load_options(
        self,
        parent_values: Optional[Dict[str, Any]] = None,
    ) -> List[FilterOption]:
        """Load options — subclasses must implement."""

    def get_options(
        self,
        parent_values: Optional[Dict[str, Any]] = None,
    ) -> List[FilterOption]:
        if parent_values is None and self._cached_options is not None:
            return self._cached_options
        opts = self._load_options(parent_values)
        if parent_values is None:
            self._cached_options = opts
        return opts


class InputFilter(BaseFilter):
    """
    Base for input-type filters (text, number, daterange, toggle).
    No options to load.
    """

    def get_options(self, parent_values=None) -> List[FilterOption]:
        return []
