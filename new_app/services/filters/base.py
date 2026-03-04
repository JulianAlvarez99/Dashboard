"""
Base filter classes and dataclasses.

Defines the contract every filter must follow:
  - ``FilterOption``: single option for dropdowns/multiselects.
  - ``FilterConfig``: runtime config built from DB row + class attributes.
  - ``BaseFilter``: abstract base — now self-describing via class attributes.
  - ``OptionsFilter``: base for dropdown/multiselect (loads from cache).
  - ``InputFilter``: base for text/number/daterange/toggle (no options).

Auto-discovery: FilterEngine resolves the concrete class by converting
``filter_name`` (CamelCase) to a snake_case module path and importing it.
Class attributes replace FILTER_REGISTRY entirely.
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
    pydantic_type: str = "Any"
    js_behavior: Dict[str, str] = field(default_factory=lambda: {
        "serialize": "raw",
        "include_if": "truthy",
        "on_change": "",
    })

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
            "pydantic_type": self.pydantic_type,
            "js_behavior": self.js_behavior,
        }


# ─────────────────────────────────────────────────────────────
#  ABSTRACT BASES
# ─────────────────────────────────────────────────────────────

class BaseFilter(ABC):
    """
    Abstract base for every filter type.

    Class attributes (override in each concrete filter):
      filter_type    : "daterange" | "dropdown" | "multiselect" | ...
      param_name     : HTTP param name sent from the frontend.
      options_source : cache key for dynamic options, or None.
      default_value  : default when user provides nothing.
      placeholder    : input placeholder text, or None.
      required       : whether a value is mandatory.
      depends_on     : param_name of parent filter for cascade, or None.
      ui_config      : extra frontend rendering hints.

    Subclasses **must** implement:
      - ``validate(value)``  → bool
      - ``get_default()``    → Any

    May override:
      - ``get_options(parent_values)``  → list[FilterOption]
      - ``to_sql_clause(value)``        → tuple[str, dict] | None
    """

    # ── Class-level configuration (auto-discovery) ─────────────
    filter_type    : str               = ""
    param_name     : str               = ""
    options_source : Optional[str]     = None
    default_value  : Any               = None
    placeholder    : Optional[str]     = None
    required       : bool              = False
    depends_on     : Optional[str]     = None
    ui_config      : Dict[str, Any]    = {}

    # ── Frontend contract (Fase 1 — filter_refactor_plan) ────
    pydantic_type : str           = "Any"
    js_behavior   : Dict[str,str] = {
        "serialize":  "raw",
        "include_if": "truthy",
        "on_change":  "",
    }
    js_inline     : Optional[str] = None

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
        """Full serialization including resolved options and frontend contract."""
        out = self.config.to_dict()
        opts = self.get_options(parent_values)
        out["options"] = [o.to_dict() for o in opts]
        out["default_value"] = self.get_default()
        out["js_inline"] = type(self).js_inline  # class-level attribute, None or str
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
        if parent_values is None and self._cached_options:
            # Only use the cache when it is non-empty.
            # An empty list means the metadata cache was not yet loaded when
            # options were first requested — we must retry rather than return
            # a stale empty result.
            return self._cached_options
        opts = self._load_options(parent_values)
        if parent_values is None and opts:
            # Only persist non-empty results so that the next call retries if
            # the metadata cache was empty at the time of the first load.
            self._cached_options = opts
        return opts


class InputFilter(BaseFilter):
    """
    Base for input-type filters (text, number, daterange, toggle).
    No options to load.
    """

    def get_options(self, parent_values=None) -> List[FilterOption]:
        return []
