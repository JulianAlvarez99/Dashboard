"""
Specific widget type implementations
"""

from .kpi_production import KPIProductionWidget
from .kpi_weight import KPIWeightWidget
from .kpi_oee import KPIOEEWidget
from .kpi_downtime import KPIDowntimeWidget
from .line_chart import LineChartWidget
from .bar_chart import BarChartWidget
from .pie_chart import PieChartWidget
from .comparison_bar import ComparisonBarWidget
from .downtime_table import DowntimeTableWidget
from .scatter_chart import ScatterChartWidget

__all__ = [
    'KPIProductionWidget',
    'KPIWeightWidget',
    'KPIOEEWidget',
    'KPIDowntimeWidget',
    'LineChartWidget',
    'BarChartWidget',
    'PieChartWidget',
    'ComparisonBarWidget',
    'DowntimeTableWidget',
    'ScatterChartWidget'
]
