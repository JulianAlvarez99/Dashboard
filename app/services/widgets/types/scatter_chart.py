from typing import Any, Dict
import pandas as pd
from app.services.widgets.base import ChartWidget

class ScatterChartWidget(ChartWidget):
    """
    Widget for rendering scatter charts.
    Expects data in the form of a DataFrame with 'x' and 'y' columns.
    """

    async def _process_chart_data(self, df: pd.DataFrame, **kwargs) -> Dict[str, Any]:
        """
        Process the input DataFrame to extract x and y values for the scatter chart.

        Args:
            df: DataFrame containing at least 'x' and 'y' columns.

        Returns:
            A dictionary with 'x' and 'y' lists for plotting.
        """
        if df.empty:
            return {"datasets": []}
        
        # Lógica de transformación: Extraer hora y duración
        # Asumimos que 'timestamp' y 'duration_seconds' existen en el DF
        data_points = []
        
        # Optimizacion: Usar itertuples es más rápido que iterrows
        for row in df.itertuples():
            data_points.append({
                'x': row.timestamp.hour + (row.timestamp.minute / 60), # Hora decimal
                'y': row.duration_seconds
            })

        return {
            "datasets": [{
                "label": "Paradas vs Hora",
                "data": data_points,
                "backgroundColor": "rgba(255, 99, 132, 0.5)"
            }]
        }