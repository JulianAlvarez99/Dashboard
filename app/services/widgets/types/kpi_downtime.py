"""
KPI: Downtime Count Widget
"""

from app.services.widgets.base import KPIWidget, FilterParams


class KPIDowntimeWidget(KPIWidget):
    """
    Shows count of downtime events.
    
    TODO: Requires downtime_events table integration.
    """
    
    async def _calculate_value(self, params: FilterParams) -> float:
        """Calculate downtime count"""
        # TODO: Query downtime_events table
        # SELECT COUNT(*) FROM downtime_events
        # WHERE line_id IN (...)
        # AND start_time BETWEEN ... AND ...
        
        return 0.0
    
    def _get_unit(self) -> str:
        """Unit for downtime"""
        return "paradas"
    
    async def render(self, params: FilterParams):
        """Override to include downtime duration"""
        data = {
            "value": 0,
            "unit": "paradas",
            "total_minutes": 0,
            "trend": None
        }
        
        return self._create_widget_data(
            data=data,
            metadata={
                "widget_category": "kpi",
                "note": "Downtime integration pending"
            }
        )
