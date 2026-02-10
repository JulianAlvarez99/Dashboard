"""
Ranking & summary processors package — re-exports every processor function.

Importing ``from app.services.processors.ranking import process_product_ranking``
still works exactly as before; each processor now lives in its own module.
"""

from app.services.processors.ranking.product_ranking import process_product_ranking
from app.services.processors.ranking.line_status import process_line_status
from app.services.processors.ranking.metrics_summary import process_metrics_summary

__all__ = [
    "process_product_ranking",
    "process_line_status",
    "process_metrics_summary",
]
