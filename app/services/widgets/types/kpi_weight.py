"""
KPI: Total Weight Widget
"""

from app.services.widgets.base import KPIWidget, FilterParams
from app.services.widgets.aggregators import DataAggregator


class KPIWeightWidget(KPIWidget):
    """
    Shows total weight of production.
    """
    
    async def _calculate_value(self, params: FilterParams) -> float:
        """Calculate total weight"""
        aggregator = DataAggregator(self.session)
        line_ids = aggregator.get_line_ids_from_params(params)
        
        df = await aggregator.fetch_detections_multi_line(line_ids, params)
        
        if df.empty:
            return 0.0
        
        df = aggregator.enrich_with_metadata(df)
        total_weight = aggregator.calculate_total_weight(df)
        
        return round(total_weight, 2)
    
    def _get_unit(self) -> str:
        """Unit for weight"""
        return "kg"
