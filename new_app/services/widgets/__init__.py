"""
Widget Engine — Etapa 5.

Modules:
  base           : BaseWidget ABC and WidgetResult dataclass.
  engine         : WidgetEngine — dynamic instantiation via Registry Pattern.
  helpers        : Shared utilities (scheduled minutes, shift helpers, formatters).
  types/         : Concrete widget implementations (KPI, Chart, Table, etc.).
"""

from new_app.services.widgets.base import BaseWidget, WidgetResult
from new_app.services.widgets.engine import WidgetEngine, widget_engine

__all__ = ["BaseWidget", "WidgetResult", "WidgetEngine", "widget_engine"]
