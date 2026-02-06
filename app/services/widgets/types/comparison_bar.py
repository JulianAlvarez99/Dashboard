"""
Comparison Bar: Entrada vs Salida vs Descarte Widget
"""

from typing import Dict, Any, List
import pandas as pd

from app.services.widgets.base import ChartWidget, FilterParams
from app.services.widgets.aggregators import DataAggregator
from app.core.cache import metadata_cache


class ComparisonBarWidget(ChartWidget):
    """
    Shows comparison between entrada (input), salida (output), and descarte.
    Descarte = Entrada - Salida (only for lines with both input+output areas).
    """
    
    async def _fetch_data(self, params: FilterParams) -> pd.DataFrame:
        """Fetch detection data"""
        aggregator = DataAggregator(self.session)
        line_ids = aggregator.get_line_ids_from_params(params)
        
        df = await aggregator.fetch_detections_multi_line(line_ids, params)
        
        if not df.empty:
            df = aggregator.enrich_with_metadata(df)
        
        return df
    
    def _get_lines_with_input_output(self, line_ids: List[int]) -> List[int]:
        """Return line IDs that have both input and output areas."""
        result = []
        for lid in line_ids:
            areas = metadata_cache.get_areas_by_line(lid)
            types = {a["area_type"] for a in areas}
            if "input" in types and "output" in types:
                result.append(lid)
        return result

    async def _process_chart_data(
        self,
        df: pd.DataFrame,
        params: FilterParams
    ) -> Dict[str, Any]:
        """Process into comparison bar format"""
        # Only use input and output areas (ignore process)
        relevant_df = df[df["area_type"].isin(["input", "output"])]
        
        salida = int(len(relevant_df[relevant_df["area_type"] == "output"]))
        
        # Entrada/descarte only from lines with both areas
        aggregator = DataAggregator(self.session)
        line_ids = aggregator.get_line_ids_from_params(params)
        dual_lines = self._get_lines_with_input_output(line_ids)
        
        entrada = 0
        descarte = 0
        if dual_lines and "line_id" in relevant_df.columns:
            dual_df = relevant_df[relevant_df["line_id"].isin(dual_lines)]
            entrada = int(len(dual_df[dual_df["area_type"] == "input"]))
            salida_dual = int(len(dual_df[dual_df["area_type"] == "output"]))
            descarte = max(0, entrada - salida_dual)
        
        return {
            "labels": ["Entrada", "Salida", "Descarte"],
            "datasets": [{
                "data": [entrada, salida, descarte],
                "backgroundColor": ["#22c55e", "#3b82f6", "#ef4444"]
            }],
            "metadata": {
                "entrada": entrada,
                "salida": salida,
                "descarte": descarte
            }
        }
