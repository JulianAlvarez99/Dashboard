"""
BaseWidget — Abstract base class for all widgets.

Single Responsibility: define the contract that every widget must follow.
Widgets are "dumb processors" — they receive pre-scoped data (Data Scoping)
and return a structured JSON-ready dict.

Every concrete widget inherits from BaseWidget and implements ``process()``.
The widget does NOT know how its data was obtained (internal DB or external API).

Usage in a concrete widget::

    from new_app.services.widgets.base import BaseWidget, WidgetResult

    class KpiTotalProduction(BaseWidget):
        def process(self) -> WidgetResult:
            ...
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd


@dataclass
class WidgetContext:
    """
    Everything a widget needs to process its data.

    Populated by the WidgetEngine / DataBroker before calling ``process()``.
    """
    widget_id: int
    widget_name: str          # class name / registry key
    display_name: str         # human-readable name from widget_catalog

    # Data payload — DataFrame for internal, dict/list for external
    data: Any = None

    # Downtime data (shared across all widgets that need it)
    downtime: Optional[pd.DataFrame] = None

    # Lines that were queried
    lines_queried: List[int] = field(default_factory=list)

    # Filter params (cleaned dict from FilterEngine)
    params: Dict[str, Any] = field(default_factory=dict)

    # Widget-specific config from WIDGET_REGISTRY.default_config
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WidgetResult:
    """
    Standardized output from any widget.

    Serialized to JSON by the orchestrator (Etapa 6).
    """
    widget_id: int
    widget_name: str
    widget_type: str
    data: Any
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "widget_id": self.widget_id,
            "widget_name": self.widget_name,
            "widget_type": self.widget_type,
            "data": self.data,
            "metadata": self.metadata,
        }


class BaseWidget(ABC):
    """
    Abstract base class for all widgets.

    Subclasses MUST implement:
      - ``process()`` → WidgetResult

    The widget receives its context through ``self.ctx`` which contains
    the pre-scoped data, downtime, lines, params, and config.
    """

    def __init__(self, ctx: WidgetContext) -> None:
        self.ctx = ctx

    @abstractmethod
    def process(self) -> WidgetResult:
        """
        Process the input data and return a structured result.

        Returns:
            WidgetResult with the widget's processed data.
        """
        ...

    # ── Convenience properties ───────────────────────────────────

    @property
    def widget_id(self) -> int:
        return self.ctx.widget_id

    @property
    def widget_name(self) -> str:
        return self.ctx.widget_name

    @property
    def display_name(self) -> str:
        return self.ctx.display_name

    @property
    def df(self) -> pd.DataFrame:
        """Shorthand for the detection DataFrame."""
        if isinstance(self.ctx.data, pd.DataFrame):
            return self.ctx.data
        return pd.DataFrame()

    @property
    def downtime_df(self) -> pd.DataFrame:
        """Shorthand for the downtime DataFrame."""
        if self.ctx.downtime is not None:
            return self.ctx.downtime
        return pd.DataFrame()

    @property
    def has_downtime(self) -> bool:
        return not self.downtime_df.empty

    # ── Result builders ──────────────────────────────────────────

    def _result(
        self,
        widget_type: str,
        data: Any,
        **meta: Any,
    ) -> WidgetResult:
        """Shorthand to build a WidgetResult."""
        return WidgetResult(
            widget_id=self.widget_id,
            widget_name=self.display_name,
            widget_type=widget_type,
            data=data,
            metadata={"widget_category": meta.pop("category", widget_type), **meta},
        )

    def _empty(self, widget_type: str) -> WidgetResult:
        """Build a standard empty-data result."""
        return WidgetResult(
            widget_id=self.widget_id,
            widget_name=self.display_name,
            widget_type=widget_type,
            data=None,
            metadata={"empty": True, "message": "No hay datos disponibles"},
        )
