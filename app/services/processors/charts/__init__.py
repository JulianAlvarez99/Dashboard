"""
Chart processors package — re-exports every chart processor function.

Importing ``from app.services.processors.charts import process_line_chart``
still works exactly as before; the only change is that each processor
now lives in its own module for SRP compliance.
"""

from app.services.processors.charts.line_chart import process_line_chart
from app.services.processors.charts.bar_chart import process_bar_chart
from app.services.processors.charts.pie_chart import process_pie_chart
from app.services.processors.charts.comparison_bar import process_comparison_bar
from app.services.processors.charts.scatter_chart import process_scatter_chart

__all__ = [
    "process_line_chart",
    "process_bar_chart",
    "process_pie_chart",
    "process_comparison_bar",
    "process_scatter_chart",
]
