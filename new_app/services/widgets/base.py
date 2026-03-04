"""
BaseWidget — Abstract base class for all widgets.

Single Responsibility: define the contract that every widget must follow.
Widgets are self-describing via class attributes — no external registry needed.

Each widget is completely self-contained in its .py file:
  - Data requirements (required_columns, default_config)
  - Rendering behavior (render, chart_type, chart_height)
  - Layout (tab, col_span, row_span, order, downtime_only)
  - JS chart config (js_inline for chart widgets)

Auto-discovery pattern::

    DB: widget_catalog.widget_name = "KpiTotalProduction"
        ↓  CamelCase → snake_case (WidgetEngine)
    kpi_total_production.py
        ↓  importlib
    class KpiTotalProduction(BaseWidget):
        required_columns = ["area_type"]   # data requirements
        render           = "kpi"           # frontend render type
        tab              = "produccion"    # layout
        ...
        def process(self) -> WidgetResult: ...

Adding a new widget = 1 file + 1 DB INSERT. Zero additional files.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional, Type

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

    Class attributes (override in each subclass):

      Data requirements:
        required_columns → list of DF columns the widget needs (Data Scoping)
        default_config   → default config dict passed via self.ctx.config

      Rendering behavior:
        render           → frontend partial type: "kpi"|"kpi_oee"|"chart"|
                           "table"|"indicator"|"summary"|"feed"|"unknown"
        chart_type       → only for render="chart": "line_chart"|"bar_chart"|
                           "pie_chart"|"comparison_bar"|"scatter_chart"
        chart_height     → CSS height of canvas (only for render="chart")

      Layout (replaces widget_layout.py):
        tab              → "produccion" | "oee" tab where widget appears
        col_span         → 1-4 grid columns the widget spans
        row_span         → 1-2 grid rows the widget spans
        order            → numeric order in the grid
        downtime_only    → hide in multi-line mode

      JS inline (for chart widgets):
        js_inline        → JS string that registers buildConfig in
                           WidgetChartBuilders (or None for non-chart)
    """

    # ── Data requirements (override in subclass) ─────────────────
    required_columns: List[str] = []
    default_config:   Dict[str, Any] = {}

    # ── Rendering behavior (override in subclass) ────────────────
    render:       str = "kpi"
    chart_type:   str = ""
    chart_height: str = "250px"

    # ── Layout (replaces widget_layout.py) ───────────────────────
    # These attributes are the source of truth for visual positioning.
    # The widget knows where it lives — no external dict lookup needed.
    tab:          str  = "produccion"  # "produccion" | "oee"
    col_span:     int  = 1             # 1–4 (grid de 4 columnas)
    row_span:     int  = 1             # 1–2 filas
    order:        int  = 0             # orden en el grid
    downtime_only: bool = False        # ocultar en modo multi-línea

    # ── JS inline (Chart.js config + handlers) ───────────────────
    # For chart widgets: registers buildConfig in WidgetChartBuilders.
    # For non-chart widgets: None.
    js_inline: ClassVar[Optional[str]] = None

    def __init__(self, ctx: WidgetContext) -> None:
        self.ctx = ctx

    @classmethod
    def get_layout(cls) -> Dict[str, Any]:
        """
        Return layout metadata as dict — replaces WIDGET_LAYOUT lookup.
        Called by routes/dashboard.py _enrich_widgets().
        """
        return {
            "tab":           cls.tab,
            "col_span":      cls.col_span,
            "row_span":      cls.row_span,
            "order":         cls.order,
            "downtime_only": cls.downtime_only,
            "render":        cls.render,
            "chart_type":    cls.chart_type,
            "chart_height":  cls.chart_height,
        }

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
            widget_name=self.widget_name,  # class name for WidgetChartBuilders lookup
            widget_type=widget_type,
            data=data,
            metadata={
                "widget_category": meta.pop("category", widget_type),
                "display_name": self.display_name,  # human-readable name for UI
                **meta,
            },
        )

    def _empty(self, widget_type: str) -> WidgetResult:
        """Build a standard empty-data result."""
        return WidgetResult(
            widget_id=self.widget_id,
            widget_name=self.widget_name,  # class name for WidgetChartBuilders lookup
            widget_type=widget_type,
            data=None,
            metadata={
                "empty": True,
                "message": "No hay datos disponibles",
                "display_name": self.display_name,
            },
        )
