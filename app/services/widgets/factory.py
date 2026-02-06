"""
Widget Factory - Creates widget instances based on type
"""

from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.widgets.base import BaseWidget, WidgetConfig
from app.services.widgets.types import (
    KPIProductionWidget,
    KPIWeightWidget,
    KPIOEEWidget,
    KPIDowntimeWidget,
    LineChartWidget,
    BarChartWidget,
    PieChartWidget,
    ComparisonBarWidget,
    DowntimeTableWidget
)


class WidgetFactory:
    """
    Factory for creating widget instances.
    Maps widget types and names to their implementation classes.
    """
    
    # Direct type mapping
    _type_map = {
        "kpi_total_production": KPIProductionWidget,
        "kpi_total_weight": KPIWeightWidget,
        "kpi_oee": KPIOEEWidget,
        "kpi_downtime_count": KPIDowntimeWidget,
        "line_chart": LineChartWidget,
        "bar_chart": BarChartWidget,
        "pie_chart": PieChartWidget,
        "comparison_bar": ComparisonBarWidget,
        "downtime_table": DowntimeTableWidget,
    }
    
    # Keyword mapping for smart detection based on widget name
    _keyword_map = {
        "produccion_total": KPIProductionWidget,
        "total_production": KPIProductionWidget,
        "peso_total": KPIWeightWidget,
        "total_weight": KPIWeightWidget,
        "oee": KPIOEEWidget,
        "paradas": KPIDowntimeWidget,
        "downtime": KPIDowntimeWidget,
        "linea": LineChartWidget,
        "line_chart": LineChartWidget,
        "temporal": LineChartWidget,
        "barra": BarChartWidget,
        "bar_chart": BarChartWidget,
        "torta": PieChartWidget,
        "pie": PieChartWidget,
        "distribucion": PieChartWidget,
        "comparativa": ComparisonBarWidget,
        "comparison": ComparisonBarWidget,
        "tabla": DowntimeTableWidget,
        "table": DowntimeTableWidget,
    }
    
    @classmethod
    def create(
        cls,
        config: WidgetConfig,
        session: AsyncSession
    ) -> Optional[BaseWidget]:
        """
        Create a widget instance from configuration.
        
        Args:
            config: Widget configuration
            session: Database session
            
        Returns:
            Widget instance or None if type not supported
        """
        # Try exact type match first
        widget_class = cls._type_map.get(config.widget_type)
        
        # If no exact match, try keyword detection from widget name
        if not widget_class:
            widget_class = cls._detect_from_name(config.widget_name)
        
        if not widget_class:
            return None
        
        return widget_class(config, session)
    
    @classmethod
    def create_from_dict(
        cls,
        data: Dict[str, Any],
        session: AsyncSession
    ) -> Optional[BaseWidget]:
        """
        Create a widget from a dictionary (e.g., from database).
        
        Args:
            data: Dictionary with widget configuration
            session: Database session
            
        Returns:
            Widget instance or None
        """
        config = WidgetConfig(
            widget_id=data["widget_id"],
            widget_name=data["widget_name"],
            widget_type=data.get("widget_type", "unknown"),
            description=data.get("description"),
            size=data.get("size", "medium"),
            refresh_interval=data.get("refresh_interval"),
            ui_config=data.get("ui_config")
        )
        
        return cls.create(config, session)
    
    @classmethod
    def _detect_from_name(cls, widget_name: str) -> Optional[type]:
        """
        Detect widget class from name using keywords.
        
        Args:
            widget_name: Name of the widget
            
        Returns:
            Widget class or None
        """
        name_lower = widget_name.lower().replace(" ", "_")
        
        # Check each keyword
        for keyword, widget_class in cls._keyword_map.items():
            if keyword in name_lower:
                return widget_class
        
        return None
    
    @classmethod
    def register_widget_type(
        cls,
        widget_type: str,
        widget_class: type,
        keywords: Optional[list] = None
    ):
        """
        Register a new custom widget type.
        
        Args:
            widget_type: Type identifier
            widget_class: Class implementing BaseWidget
            keywords: Optional keywords for name detection
        """
        cls._type_map[widget_type] = widget_class
        
        if keywords:
            for keyword in keywords:
                cls._keyword_map[keyword] = widget_class
    
    @classmethod
    def get_supported_types(cls) -> list:
        """Get list of supported widget types"""
        return list(cls._type_map.keys())
    
    @classmethod
    def get_widget_category(cls, widget_type: str) -> str:
        """
        Get the category of a widget type (kpi, chart, table).
        
        Args:
            widget_type: Widget type identifier
            
        Returns:
            Category name
        """
        if widget_type.startswith("kpi_"):
            return "kpi"
        elif "chart" in widget_type:
            return "chart"
        elif "table" in widget_type:
            return "table"
        else:
            return "unknown"
