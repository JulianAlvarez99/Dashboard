"""
Line Chart: Time Series Widget
"""

from typing import Dict, Any
import pandas as pd

from app.services.widgets.base import ChartWidget, FilterParams
from app.services.widgets.aggregators import DataAggregator


class LineChartWidget(ChartWidget):
    """
    Shows production over time as a line chart.
    """
    
    async def _fetch_data(self, params: FilterParams) -> pd.DataFrame:
        """Fetch detection data"""
        aggregator = DataAggregator(self.session)
        line_ids = aggregator.get_line_ids_from_params(params)
        
        df = await aggregator.fetch_detections_multi_line(line_ids, params)
        
        return df
    
    async def _process_chart_data(
        self,
        df: pd.DataFrame,
        params: FilterParams
    ) -> Dict[str, Any]:
        """Process into line chart format"""
        aggregator = DataAggregator(self.session)
        
        # Resample by interval
        series = aggregator.resample_time_series(df, params.interval)
        
        return {
            "labels": [str(idx) for idx in series.index.tolist()],
            "datasets": [{
                "label": "Producción",
                "data": series.values.tolist()
            }]
        }
