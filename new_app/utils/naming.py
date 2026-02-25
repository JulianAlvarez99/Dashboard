"""
Naming utilities — CamelCase / snake_case conversions.

Single canonical implementation used by both WidgetEngine and
FilterEngine to avoid dual maintenance of the same algorithm.
"""

import re


def camel_to_snake(name: str) -> str:
    """
    Convert a CamelCase class name to a snake_case module file name.

    Examples::

        camel_to_snake("DateRangeFilter")       → "date_range_filter"
        camel_to_snake("KpiTotalProduction")    → "kpi_total_production"
        camel_to_snake("ProductionTimeChart")   → "production_time_chart"
        camel_to_snake("CurveTypeFilter")       → "curve_type_filter"
    """
    # Handle sequences like "KPIValue" → "KPI_Value" before lowercasing
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    s = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s)
    return s.lower()
