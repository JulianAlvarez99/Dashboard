"""
Widget processors — re-export all processor functions for easy importing.

Usage in dashboard_data_service.py:
    from app.services.processors import PROCESSOR_MAP
"""

from __future__ import annotations

from typing import Dict, Any, Callable, TYPE_CHECKING

# KPI processors
from app.services.processors.kpi import (
    process_kpi_production,
    process_kpi_weight,
    process_kpi_oee,
    process_kpi_downtime,
    process_kpi_availability,
    process_kpi_performance,
    process_kpi_quality,
)

# Chart processors
from app.services.processors.charts import (
    process_line_chart,
    process_bar_chart,
    process_pie_chart,
    process_comparison_bar,
)

# Table processors
from app.services.processors.tables import (
    process_downtime_table,
)

# Ranking & summary processors
from app.services.processors.ranking import (
    process_product_ranking,
    process_line_status,
    process_metrics_summary,
)

# Helpers (for direct import if needed)
from app.services.processors.helpers import (
    empty_widget,
    format_time_labels,
    calculate_scheduled_minutes,
    get_lines_with_input_output,
    strip_accents,
    infer_widget_type,
)

if TYPE_CHECKING:
    from app.services.dashboard_data_service import DashboardData
    from app.services.widgets.aggregators import DataAggregator

# ── Processor registry ───────────────────────────────────────────────
# Maps widget_type → processor function.
#
# KPI processors:   (widget_id, name, wtype, data) → dict
# Chart processors:  (widget_id, name, wtype, data, aggregator) → dict
# Table processors:  (widget_id, name, wtype, data) → dict
#
# The orchestrator is responsible for passing the right arguments.

PROCESSOR_MAP: Dict[str, Callable[..., Dict[str, Any]]] = {
    # KPIs
    "kpi_total_production": process_kpi_production,
    "kpi_total_weight": process_kpi_weight,
    "kpi_oee": process_kpi_oee,
    "kpi_downtime_count": process_kpi_downtime,
    "kpi_availability": process_kpi_availability,
    "kpi_performance": process_kpi_performance,
    "kpi_quality": process_kpi_quality,
    # Charts
    "line_chart": process_line_chart,
    "bar_chart": process_bar_chart,
    "pie_chart": process_pie_chart,
    "comparison_bar": process_comparison_bar,
    # Tables
    "downtime_table": process_downtime_table,
    # Ranking & summary
    "product_ranking": process_product_ranking,
    "line_status": process_line_status,
    "metrics_summary": process_metrics_summary,
}

# Categories for the orchestrator to know which signature to use
CHART_TYPES = {
    "line_chart", "bar_chart", "pie_chart", "comparison_bar",
    "product_ranking", "line_status", "metrics_summary",
}

__all__ = [
    "PROCESSOR_MAP",
    "CHART_TYPES",
    # KPI
    "process_kpi_production",
    "process_kpi_weight",
    "process_kpi_oee",
    "process_kpi_downtime",
    "process_kpi_availability",
    "process_kpi_performance",
    "process_kpi_quality",
    # Charts
    "process_line_chart",
    "process_bar_chart",
    "process_pie_chart",
    "process_comparison_bar",
    # Tables
    "process_downtime_table",
    # Helpers
    "empty_widget",
    "format_time_labels",
    "calculate_scheduled_minutes",
    "get_lines_with_input_output",
    "strip_accents",
    "infer_widget_type",
]
