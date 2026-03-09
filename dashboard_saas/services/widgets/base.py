"""
BaseWidget — Base class for all widgets.

Phase 3: Only auto-discovery. No data processing yet.
Processing (process method) will be added in a future phase.

Naming convention (same as filters):
    DB widget_name:  "KpiTotalProduction"  (CamelCase)
    Python file:     kpi_total_production.py
    Python class:    KpiTotalProduction
    JS file:         kpi_total_production.js
"""

from dataclasses import dataclass, field
from typing import Any, Dict

from dashboard_saas.services.filters.base import camel_to_snake


@dataclass
class WidgetConfig:
    """
    Runtime configuration for a widget instance.
    Merges DB row data with class-level attributes.
    """
    widget_id: int
    widget_name: str       # CamelCase, e.g. "KpiTotalProduction"
    description: str


class BaseWidget:
    """
    Base class that all widgets must extend.

    Phase 3: Only stores config and provides serialization.
    Phase 4+: Will add process(df) → WidgetResult.
    """

    # ── Class-level attributes (overridden by each subclass) ────
    render: str = "kpi"          # "kpi", "chart", "table", etc.
    chart_type: str = ""         # "line", "bar", "pie", etc. (for charts)
    tab: str = "produccion"      # UI tab where this widget appears
    col_span: int = 1            # Grid column span
    row_span: int = 1            # Grid row span
    order: int = 0               # Display order within the tab

    def __init__(self, config: WidgetConfig):
        self.config = config

    @property
    def js_file(self) -> str:
        """JS filename derived from class name."""
        return camel_to_snake(self.__class__.__name__) + ".js"

    def to_dict(self) -> Dict:
        """Serialize for frontend rendering."""
        return {
            "widget_id": self.config.widget_id,
            "widget_name": self.config.widget_name,
            "description": self.config.description,
            "render": self.render,
            "chart_type": self.chart_type,
            "tab": self.tab,
            "col_span": self.col_span,
            "row_span": self.row_span,
            "order": self.order,
            "js_file": self.js_file,
        }
