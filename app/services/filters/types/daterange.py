"""
DateRange Filter - Handles date/time range selection
"""

from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional

from app.services.filters.base import InputFilter, FilterConfig


class DateRangeFilter(InputFilter):
    """
    Filter for selecting date ranges with optional time components.
    
    Params generated:
    - start_date, start_time, end_date, end_time
    or
    - start_datetime, end_datetime
    """
    
    def __init__(self, config: FilterConfig):
        super().__init__(config)
    
    def get_default_value(self) -> Dict[str, Any]:
        """
        Get default date range.
        Default: last 7 days ending today
        """
        default = self.config.default_value or {}
        days_back = default.get("days_back", 7)
        
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)
        
        return {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "start_time": default.get("start_time", "00:00"),
            "end_time": default.get("end_time", "23:59")
        }
    
    def validate_value(self, value: Dict[str, Any]) -> bool:
        """Validate date range"""
        if not super().validate_value(value):
            return False
        
        if not isinstance(value, dict):
            return False
        
        required_keys = {"start_date", "end_date"}
        if not required_keys.issubset(value.keys()):
            return False
        
        # Validate start <= end
        try:
            start = date.fromisoformat(value["start_date"])
            end = date.fromisoformat(value["end_date"])
            return start <= end
        except (ValueError, TypeError):
            return False
    
    def parse_to_datetime(self, value: Dict[str, Any]) -> Dict[str, datetime]:
        """
        Convert date/time strings to datetime objects.
        
        Returns:
            Dict with start_datetime and end_datetime
        """
        start_date = date.fromisoformat(value["start_date"])
        end_date = date.fromisoformat(value["end_date"])
        
        start_time_str = value.get("start_time", "00:00")
        end_time_str = value.get("end_time", "23:59")
        
        start_hour, start_min = map(int, start_time_str.split(":"))
        end_hour, end_min = map(int, end_time_str.split(":"))
        
        return {
            "start_datetime": datetime.combine(start_date, datetime.min.time()).replace(
                hour=start_hour, minute=start_min
            ),
            "end_datetime": datetime.combine(end_date, datetime.min.time()).replace(
                hour=end_hour, minute=end_min
            )
        }
