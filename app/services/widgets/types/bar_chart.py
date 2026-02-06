"""
Bar Chart: Distribution by Category Widget
"""

from typing import Dict, Any
import pandas as pd

from app.services.widgets.base import ChartWidget, FilterParams
from app.services.widgets.aggregators import DataAggregator


class BarChartWidget(ChartWidget):
    """
    Shows distribution by category (e.g., by area).
    """
    
    async def _fetch_data(self, params: FilterParams) -> pd.DataFrame:
        """Fetch detection data"""
        aggregator = DataAggregator(self.session)
        line_ids = aggregator.get_line_ids_from_params(params)
        
        df = await aggregator.fetch_detections_multi_line(line_ids, params)
        
        if not df.empty:
            df = aggregator.enrich_with_metadata(df)
        
        return df
    
    async def _process_chart_data(
        self,
        df: pd.DataFrame,
        params: FilterParams
    ) -> Dict[str, Any]:
        """Process into bar chart format"""
        aggregator = DataAggregator(self.session)
        
        # Aggregate by area
        series = aggregator.aggregate_by_column(df, "area_name", ascending=False)
        
        return {
            "labels": series.index.tolist(),
            "datasets": [{
                "label": "Detecciones por Área",
                "data": series.values.tolist()
            }]
        }
