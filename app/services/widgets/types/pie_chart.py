"""
Pie Chart: Distribution Widget
"""

from typing import Dict, Any
import pandas as pd

from app.services.widgets.base import ChartWidget, FilterParams
from app.services.widgets.aggregators import DataAggregator


class PieChartWidget(ChartWidget):
    """
    Shows distribution as a pie chart (e.g., by product).
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
        """Process into pie chart format"""
        # Group by product with colors
        grouped = df.groupby(["product_name", "product_color"]).size().reset_index(name="count")
        
        return {
            "labels": grouped["product_name"].tolist(),
            "datasets": [{
                "data": grouped["count"].tolist(),
                "backgroundColor": grouped["product_color"].tolist()
            }]
        }
