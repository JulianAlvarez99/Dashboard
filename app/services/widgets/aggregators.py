"""
Data aggregation utilities shared across widgets
Handles common data fetching and enrichment patterns
"""

from typing import Dict, List, Optional
import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import metadata_cache
from app.services.widgets.base import FilterParams


class DataAggregator:
    """
    Utility class for fetching and enriching detection data.
    Eliminates duplication across widget types.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def fetch_detections(
        self,
        line_id: int,
        params: FilterParams
    ) -> pd.DataFrame:
        """
        Fetch raw detection data for a single production line.
        
        Args:
            line_id: Production line ID
            params: Filter parameters
            
        Returns:
            DataFrame with detection data
        """
        line = metadata_cache.get_production_line(line_id)
        if not line:
            return pd.DataFrame()
        
        table_name = f"detection_line_{line['line_name'].lower()}"
        
        query, bind_params = self._build_detection_query(table_name, params)
        
        try:
            result = await self.session.execute(text(query), bind_params)
            rows = result.mappings().all()
            return pd.DataFrame([dict(row) for row in rows])
        except Exception:
            return pd.DataFrame()
    
    async def fetch_detections_multi_line(
        self,
        line_ids: List[int],
        params: FilterParams
    ) -> pd.DataFrame:
        """
        Fetch detection data for multiple production lines.
        
        Args:
            line_ids: List of production line IDs
            params: Filter parameters
            
        Returns:
            Combined DataFrame from all lines
        """
        dataframes = []
        
        for line_id in line_ids:
            df = await self.fetch_detections(line_id, params)
            if not df.empty:
                df["line_id"] = line_id
                dataframes.append(df)
        
        if not dataframes:
            return pd.DataFrame()
        
        return pd.concat(dataframes, ignore_index=True)
    
    def _build_detection_query(
        self,
        table_name: str,
        params: FilterParams
    ) -> tuple[str, Dict]:
        """
        Build SQL query for detection data with filters.
        Uses partition pruning hints when date filters are present.
        
        Returns:
            Tuple of (query_string, bind_params)
        """
        query = f"""
            SELECT detection_id, detected_at, area_id, product_id
            FROM {table_name}
            WHERE 1=1
        """
        
        bind_params = {}
        
        # Resolve effective start/end datetimes
        effective_start, effective_end = params.get_effective_datetimes()
        
        if effective_start:
            query += " AND detected_at >= :start_dt"
            bind_params["start_dt"] = effective_start
        
        if effective_end:
            query += " AND detected_at <= :end_dt"
            bind_params["end_dt"] = effective_end
        
        # Area filter (use numbered placeholders for IN clause)
        if params.area_ids:
            placeholders = ", ".join(
                f":area_id_{i}" for i in range(len(params.area_ids))
            )
            query += f" AND area_id IN ({placeholders})"
            for i, aid in enumerate(params.area_ids):
                bind_params[f"area_id_{i}"] = aid
        
        # Product filter (use numbered placeholders for IN clause)
        if params.product_ids:
            placeholders = ", ".join(
                f":product_id_{i}" for i in range(len(params.product_ids))
            )
            query += f" AND product_id IN ({placeholders})"
            for i, pid in enumerate(params.product_ids):
                bind_params[f"product_id_{i}"] = pid
        
        # Shift time-of-day filter — restrict detections to the shift window
        if params.shift_id:
            shift = metadata_cache.get_shifts().get(params.shift_id)
            if shift:
                s_time = shift.get("start_time")
                e_time = shift.get("end_time")
                is_overnight = shift.get("is_overnight", False)
                # Convert timedelta/time to "HH:MM:SS" string
                s_str = self._time_to_str(s_time)
                e_str = self._time_to_str(e_time)
                if s_str and e_str:
                    if is_overnight or e_str <= s_str:
                        # Overnight shift e.g. 22:00 → 06:00
                        query += " AND (TIME(detected_at) >= :shift_start OR TIME(detected_at) < :shift_end)"
                    else:
                        query += " AND TIME(detected_at) >= :shift_start AND TIME(detected_at) < :shift_end"
                    bind_params["shift_start"] = s_str
                    bind_params["shift_end"] = e_str
        
        query += " ORDER BY detected_at"
        
        return query, bind_params
    
    @staticmethod
    def _time_to_str(value) -> Optional[str]:
        """Convert timedelta or time object to 'HH:MM:SS' string."""
        from datetime import timedelta
        if isinstance(value, timedelta):
            total = int(value.total_seconds())
            h, rem = divmod(total, 3600)
            m, s = divmod(rem, 60)
            return f"{h:02d}:{m:02d}:{s:02d}"
        if hasattr(value, "hour"):
            return f"{value.hour:02d}:{value.minute:02d}:{value.second:02d}"
        return None
    
    def enrich_with_metadata(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Enrich detection DataFrame with metadata from cache.
        
        Adds columns:
        - area_name, area_type
        - product_name, product_code, product_weight, product_color
        
        Args:
            df: DataFrame with detection data
            
        Returns:
            Enriched DataFrame
        """
        if df.empty:
            return df
        
        areas = metadata_cache.get_areas()
        products = metadata_cache.get_products()
        
        # Enrich area data
        df["area_name"] = df["area_id"].map(
            lambda x: areas.get(x, {}).get("area_name", "Unknown")
        )
        df["area_type"] = df["area_id"].map(
            lambda x: areas.get(x, {}).get("area_type", "Unknown")
        )
        
        # Enrich product data
        df["product_name"] = df["product_id"].map(
            lambda x: products.get(x, {}).get("product_name", "Unknown")
        )
        df["product_code"] = df["product_id"].map(
            lambda x: products.get(x, {}).get("product_code", "")
        )
        df["product_weight"] = df["product_id"].map(
            lambda x: float(products.get(x, {}).get("product_weight", 0))
        )
        df["product_color"] = df["product_id"].map(
            lambda x: products.get(x, {}).get("product_color", "#888888")
        )
        
        return df
    
    def enrich_with_line_metadata(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Enrich DataFrame with production line metadata.
        
        Adds columns:
        - line_name, line_code
        
        Args:
            df: DataFrame with line_id column
            
        Returns:
            Enriched DataFrame
        """
        if df.empty or "line_id" not in df.columns:
            return df
        
        lines = metadata_cache.get_production_lines()
        
        df["line_name"] = df["line_id"].map(
            lambda x: lines.get(x, {}).get("line_name", "Unknown")
        )
        df["line_code"] = df["line_id"].map(
            lambda x: lines.get(x, {}).get("line_code", "")
        )
        
        return df
    
    def resample_time_series(
        self,
        df: pd.DataFrame,
        interval: str,
        datetime_column: str = "detected_at"
    ) -> pd.Series:
        """
        Resample time series data by interval.
        
        Args:
            df: DataFrame with datetime column
            interval: Interval (minute, hour, day, week, month)
            datetime_column: Name of datetime column
            
        Returns:
            Series with counts per interval
        """
        if df.empty:
            return pd.Series()
        
        interval_map = {
            "minute": "1min",
            "15min": "15min",
            "hour": "1h",
            "day": "1D",
            "week": "1W",
            "month": "1ME"
        }
        
        freq = interval_map.get(interval, "1h")
        
        df[datetime_column] = pd.to_datetime(df[datetime_column])
        return df.set_index(datetime_column).resample(freq).size()
    
    def aggregate_by_column(
        self,
        df: pd.DataFrame,
        column: str,
        sort_by: str = "count",
        ascending: bool = False
    ) -> pd.Series:
        """
        Aggregate data by a specific column.
        
        Args:
            df: DataFrame to aggregate
            column: Column to group by
            sort_by: How to sort (count, sum, etc.)
            ascending: Sort order
            
        Returns:
            Series with aggregated data
        """
        if df.empty:
            return pd.Series()
        
        grouped = df.groupby(column).size()
        
        if sort_by == "count":
            grouped = grouped.sort_values(ascending=ascending)
        
        return grouped
    
    def calculate_total_weight(self, df: pd.DataFrame) -> float:
        """
        Calculate total weight from enriched DataFrame.
        
        Args:
            df: Enriched DataFrame with product_weight column
            
        Returns:
            Total weight
        """
        if df.empty or "product_weight" not in df.columns:
            return 0.0
        
        return float(df["product_weight"].sum())
    
    def get_line_ids_from_params(self, params: FilterParams) -> List[int]:
        """
        Extract list of line IDs from parameters.
        
        Args:
            params: Filter parameters
            
        Returns:
            List of line IDs to query
        """
        if params.line_ids:
            return params.line_ids
        elif params.line_id:
            return [params.line_id]
        else:
            # Return all lines if none specified
            lines = metadata_cache.get_production_lines()
            return list(lines.keys())
