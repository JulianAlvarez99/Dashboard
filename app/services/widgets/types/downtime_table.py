"""
Downtime Table Widget
"""

from typing import Dict, Any
import pandas as pd

from app.services.widgets.base import TableWidget, FilterParams


class DowntimeTableWidget(TableWidget):
    """
    Shows downtime events in a table.
    
    TODO: Requires downtime_events table integration.
    """
    
    async def _fetch_data(self, params: FilterParams) -> pd.DataFrame:
        """Fetch downtime events"""
        # TODO: Query downtime_events table
        # SELECT * FROM downtime_events
        # WHERE line_id IN (...)
        # AND start_time BETWEEN ... AND ...
        # ORDER BY start_time DESC
        
        return pd.DataFrame()
    
    async def _process_table_data(
        self,
        df: pd.DataFrame,
        params: FilterParams
    ) -> Dict[str, Any]:
        """Process into table format"""
        # TODO: Format downtime events into table
        
        return {
            "columns": [
                {"key": "start_time", "label": "Inicio"},
                {"key": "end_time", "label": "Fin"},
                {"key": "duration", "label": "Duración (min)"},
                {"key": "line_name", "label": "Línea"}
            ],
            "rows": []
        }
    
    async def render(self, params: FilterParams):
        """Override to show pending message"""
        return self._create_widget_data(
            data={"columns": [], "rows": []},
            metadata={
                "widget_category": "table",
                "note": "Downtime table pending integration"
            }
        )
