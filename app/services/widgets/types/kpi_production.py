"""
KPI: Total Production Count Widget
"""

from app.services.widgets.base import KPIWidget, FilterParams
from app.services.widgets.aggregators import DataAggregator


class KPIProductionWidget(KPIWidget):
    """
    Shows total production count (number of detections).
    """
    
    async def _calculate_value(self, params: FilterParams) -> float:
        """Calculate total production count"""
        aggregator = DataAggregator(self.session)
        line_ids = aggregator.get_line_ids_from_params(params)
        
        df = await aggregator.fetch_detections_multi_line(line_ids, params)
        
        return len(df)
    
    def _get_unit(self) -> str:
        """Unit for production count"""
        return "unidades"
