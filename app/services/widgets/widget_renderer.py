"""
WidgetRenderer - Renders widgets with data from detections
Refactored to use WidgetFactory and specific widget type implementations
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import metadata_cache
from app.services.widgets.base import WidgetConfig, FilterParams, WidgetData
from app.services.widgets.factory import WidgetFactory


class WidgetRenderer:
    """
    Service for rendering widgets using WidgetFactory.
    Simplified to delegate to specific widget type implementations.
    """
    
    def __init__(self, tenant_session: AsyncSession):
        self.session = tenant_session
    
    async def render(
        self,
        widget_id: int,
        params: FilterParams
    ) -> Optional[WidgetData]:
        """
        Render a widget with the given filter parameters.
        
        Args:
            widget_id: ID of the widget to render
            params: Filter parameters
            
        Returns:
            WidgetData ready for template or None if widget not found
        """
        # Get widget metadata from cache
        widget_data = metadata_cache.get_widget(widget_id)
        if not widget_data:
            return None
        
        # Parse widget configuration
        config = self._parse_widget_config(widget_data)
        
        # Create widget instance using factory
        widget_instance = WidgetFactory.create(config, self.session)
        if not widget_instance:
            return self._create_unknown_widget_response(widget_data)
        
        # Render widget with parameters
        return await widget_instance.render(params)
    
    def _parse_widget_config(self, widget_data: dict) -> WidgetConfig:
        """
        Parse widget data from cache into WidgetConfig.
        
        Args:
            widget_data: Raw widget data from cache
            
        Returns:
            WidgetConfig instance
        """
        additional = widget_data.get("additional_widget", {})
        
        # Determine widget type from name if not explicitly set
        widget_type = additional.get("type")
        if not widget_type:
            widget_type = self._infer_widget_type(widget_data["widget_name"])
        
        return WidgetConfig(
            widget_id=widget_data["widget_id"],
            widget_name=widget_data["widget_name"],
            widget_type=widget_type,
            description=widget_data.get("description"),
            size=additional.get("size", "medium"),
            refresh_interval=additional.get("refresh_interval"),
            ui_config=additional.get("ui_config")
        )
    
    def _infer_widget_type(self, widget_name: str) -> str:
        """
        Infer widget type from name.
        
        Args:
            widget_name: Name of the widget
            
        Returns:
            Inferred widget type
        """
        name_lower = widget_name.lower()
        
        # KPI detection
        if "produccion" in name_lower or "production" in name_lower:
            if "total" in name_lower:
                return "kpi_total_production"
        if "peso" in name_lower or "weight" in name_lower:
            return "kpi_total_weight"
        if "oee" in name_lower:
            return "kpi_oee"
        if "paradas" in name_lower or "downtime" in name_lower:
            if "tabla" in name_lower or "table" in name_lower:
                return "downtime_table"
            return "kpi_downtime_count"
        
        # Chart detection
        if "linea" in name_lower or "temporal" in name_lower:
            return "line_chart"
        if "barra" in name_lower or "bar" in name_lower:
            if "comparativa" in name_lower or "comparison" in name_lower:
                return "comparison_bar"
            return "bar_chart"
        if "torta" in name_lower or "pie" in name_lower or "distribucion" in name_lower:
            return "pie_chart"
        
        return "unknown"
    
    def _create_unknown_widget_response(self, widget_data: dict) -> WidgetData:
        """
        Create response for unknown widget type.
        
        Args:
            widget_data: Widget metadata
            
        Returns:
            WidgetData with error message
        """
        return WidgetData(
            widget_id=widget_data["widget_id"],
            widget_name=widget_data["widget_name"],
            widget_type="unknown",
            data={"message": "Widget type not implemented"},
            metadata={}
        )
