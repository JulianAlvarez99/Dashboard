"""
Base classes and interfaces for widget system
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime, date

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class WidgetConfig:
    """Configuration for a widget"""
    widget_id: int
    widget_name: str
    widget_type: str
    description: Optional[str] = None
    size: str = "medium"  # small, medium, large, full
    refresh_interval: Optional[int] = None  # seconds
    ui_config: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "widget_id": self.widget_id,
            "widget_name": self.widget_name,
            "widget_type": self.widget_type,
            "description": self.description,
            "size": self.size,
            "refresh_interval": self.refresh_interval,
            "ui_config": self.ui_config or {}
        }


@dataclass
class FilterParams:
    """Parameters passed from filters to widgets"""
    line_id: Optional[int] = None
    line_ids: Optional[List[int]] = None
    area_ids: Optional[List[int]] = None
    product_ids: Optional[List[int]] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    start_time: Optional[str] = None       # HH:MM format
    end_time: Optional[str] = None         # HH:MM format
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    shift_id: Optional[int] = None
    interval: str = "hour"
    curve_type: str = "smooth"          # stepped | smooth | linear | stacked
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FilterParams":
        """Create FilterParams from dict, parsing date strings if needed"""
        start_date_val = data.get("start_date")
        end_date_val = data.get("end_date")
        
        # Parse date strings to date objects
        if isinstance(start_date_val, str) and start_date_val:
            start_date_val = date.fromisoformat(start_date_val)
        if isinstance(end_date_val, str) and end_date_val:
            end_date_val = date.fromisoformat(end_date_val)
        
        # Parse line_id
        line_id = data.get("line_id")
        if isinstance(line_id, str) and line_id:
            line_id = int(line_id)
        elif line_id == '' or line_id is None:
            line_id = None
        
        # Parse line_ids (comma-separated string or list)
        line_ids = data.get("line_ids")
        if isinstance(line_ids, str) and line_ids:
            line_ids = [int(x.strip()) for x in line_ids.split(",")]
        
        # Parse area_ids
        area_ids = data.get("area_ids")
        if isinstance(area_ids, str) and area_ids:
            area_ids = [int(x.strip()) for x in area_ids.split(",")]
        
        # Parse product_ids
        product_ids = data.get("product_ids")
        if isinstance(product_ids, str) and product_ids:
            product_ids = [int(x.strip()) for x in product_ids.split(",")]
        
        # Parse shift_id
        shift_id = data.get("shift_id")
        if isinstance(shift_id, str) and shift_id:
            shift_id = int(shift_id)
        elif shift_id == '' or shift_id is None:
            shift_id = None
        
        return cls(
            line_id=line_id,
            line_ids=line_ids if line_ids else None,
            area_ids=area_ids if area_ids else None,
            product_ids=product_ids if product_ids else None,
            start_date=start_date_val if start_date_val else None,
            end_date=end_date_val if end_date_val else None,
            start_time=data.get("start_time") or None,
            end_time=data.get("end_time") or None,
            start_datetime=data.get("start_datetime"),
            end_datetime=data.get("end_datetime"),
            shift_id=shift_id,
            interval=data.get("interval", "hour") or "hour",
            curve_type=data.get("curve_type", "smooth") or "smooth",
        )
    
    def get_effective_datetimes(self) -> tuple:
        """
        Resolve the effective start/end datetimes.
        Combines date + time if both are present, or uses datetime fields.
        
        Returns:
            Tuple of (start_datetime, end_datetime) - either can be None
        """
        start_dt = self.start_datetime
        end_dt = self.end_datetime
        
        # Combine date + time if datetime is not already set
        if not start_dt and self.start_date:
            hour, minute = 0, 0
            if self.start_time:
                parts = self.start_time.split(":")
                hour, minute = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
            start_dt = datetime.combine(
                self.start_date, datetime.min.time()
            ).replace(hour=hour, minute=minute)
        
        if not end_dt and self.end_date:
            hour, minute = 23, 59
            if self.end_time:
                parts = self.end_time.split(":")
                hour, minute = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
            end_dt = datetime.combine(
                self.end_date, datetime.min.time()
            ).replace(hour=hour, minute=minute, second=59)
        
        return start_dt, end_dt
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization"""
        return {
            "line_id": self.line_id,
            "line_ids": self.line_ids,
            "area_ids": self.area_ids,
            "product_ids": self.product_ids,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "start_datetime": self.start_datetime.isoformat() if self.start_datetime else None,
            "end_datetime": self.end_datetime.isoformat() if self.end_datetime else None,
            "shift_id": self.shift_id,
            "interval": self.interval,
            "curve_type": self.curve_type,
        }


@dataclass
class WidgetData:
    """Data prepared for widget rendering"""
    widget_id: int
    widget_name: str
    widget_type: str
    data: Any
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "widget_id": self.widget_id,
            "widget_name": self.widget_name,
            "widget_type": self.widget_type,
            "data": self.data,
            "metadata": self.metadata
        }


class BaseWidget(ABC):
    """
    Abstract base class for all widget types.
    Each widget implements its own data fetching and processing logic.
    """
    
    def __init__(
        self,
        config: WidgetConfig,
        session: AsyncSession
    ):
        self.config = config
        self.session = session
    
    @abstractmethod
    async def render(self, params: FilterParams) -> WidgetData:
        """
        Render the widget with given filter parameters.
        
        Args:
            params: Filter parameters from dashboard
            
        Returns:
            WidgetData ready for template
        """
        pass
    
    def _create_widget_data(
        self,
        data: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> WidgetData:
        """
        Helper to create WidgetData response.
        
        Args:
            data: Widget-specific data (dict, list, number, etc.)
            metadata: Additional metadata about the widget
            
        Returns:
            WidgetData instance
        """
        return WidgetData(
            widget_id=self.config.widget_id,
            widget_name=self.config.widget_name,
            widget_type=self.config.widget_type,
            data=data,
            metadata=metadata or {}
        )
    
    def _create_empty_response(self, message: str = "No hay datos disponibles") -> WidgetData:
        """
        Create an empty/error response.
        
        Args:
            message: Message to display
            
        Returns:
            WidgetData with empty state
        """
        return self._create_widget_data(
            data=None,
            metadata={"empty": True, "message": message}
        )


class KPIWidget(BaseWidget):
    """
    Base class for KPI widgets.
    KPIs show single numeric values with optional trends.
    """
    
    async def render(self, params: FilterParams) -> WidgetData:
        """Render KPI widget"""
        value = await self._calculate_value(params)
        trend = await self._calculate_trend(params)
        
        data = {
            "value": value,
            "unit": self._get_unit(),
            "trend": trend
        }
        
        return self._create_widget_data(
            data=data,
            metadata={"widget_category": "kpi"}
        )
    
    @abstractmethod
    async def _calculate_value(self, params: FilterParams) -> float:
        """Calculate the main KPI value"""
        pass
    
    async def _calculate_trend(self, params: FilterParams) -> Optional[Dict[str, Any]]:
        """
        Calculate trend (optional).
        Returns dict with "direction" (up/down/flat) and "percentage".
        """
        return None
    
    @abstractmethod
    def _get_unit(self) -> str:
        """Get the unit for this KPI (unidades, kg, %, etc.)"""
        pass


class ChartWidget(BaseWidget):
    """
    Base class for chart widgets.
    Charts have labels and datasets.
    """
    
    async def render(self, params: FilterParams) -> WidgetData:
        """Render chart widget"""
        df = await self._fetch_data(params)
        
        if df.empty:
            return self._create_empty_response()
        
        chart_data = await self._process_chart_data(df, params)
        
        return self._create_widget_data(
            data=chart_data,
            metadata={"widget_category": "chart", "total_points": len(df)}
        )
    
    @abstractmethod
    async def _fetch_data(self, params: FilterParams) -> pd.DataFrame:
        """Fetch raw data for the chart"""
        pass
    
    @abstractmethod
    async def _process_chart_data(
        self,
        df: pd.DataFrame,
        params: FilterParams
    ) -> Dict[str, Any]:
        """
        Process DataFrame into chart format.
        Returns dict with "labels" and "datasets".
        """
        pass


class TableWidget(BaseWidget):
    """
    Base class for table widgets.
    Tables have columns and rows.
    """
    
    async def render(self, params: FilterParams) -> WidgetData:
        """Render table widget"""
        df = await self._fetch_data(params)
        
        if df.empty:
            return self._create_empty_response()
        
        table_data = await self._process_table_data(df, params)
        
        return self._create_widget_data(
            data=table_data,
            metadata={"widget_category": "table", "total_rows": len(df)}
        )
    
    @abstractmethod
    async def _fetch_data(self, params: FilterParams) -> pd.DataFrame:
        """Fetch raw data for the table"""
        pass
    
    @abstractmethod
    async def _process_table_data(
        self,
        df: pd.DataFrame,
        params: FilterParams
    ) -> Dict[str, Any]:
        """
        Process DataFrame into table format.
        Returns dict with "columns" and "rows".
        """
        pass
