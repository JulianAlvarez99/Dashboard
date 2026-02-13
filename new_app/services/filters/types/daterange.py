"""
DateRangeFilter — Date/time range picker.

Generates: start_date, end_date, start_time, end_time.
SQL contribution: ``detected_at BETWEEN :start_dt AND :end_dt``
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

from new_app.services.filters.base import FilterConfig, FilterOption, InputFilter


class DateRangeFilter(InputFilter):
    """Date + optional time range selector."""

    def get_default(self) -> Dict[str, str]:
        ui = self.config.ui_config
        days_back = 7
        end = date.today()
        start = end - timedelta(days=days_back)
        return {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "start_time": ui.get("default_start_time", "00:00"),
            "end_time": ui.get("default_end_time", "23:59"),
        }

    def validate(self, value: Any) -> bool:
        if value is None:
            return not self.config.required
        if not isinstance(value, dict):
            return False
        required = {"start_date", "end_date"}
        if not required.issubset(value.keys()):
            return False
        try:
            s = date.fromisoformat(value["start_date"])
            e = date.fromisoformat(value["end_date"])
            if s > e:
                return False
            # When same day, validate start_time <= end_time
            if s == e:
                st = value.get("start_time", "00:00")
                et = value.get("end_time", "23:59")
                if st > et:
                    return False
            return True
        except (ValueError, TypeError):
            return False

    def parse_datetimes(self, value: Dict[str, str]) -> Dict[str, datetime]:
        """Convert raw strings to ``datetime`` objects."""
        sd = date.fromisoformat(value["start_date"])
        ed = date.fromisoformat(value["end_date"])
        sh, sm = map(int, value.get("start_time", "00:00").split(":"))
        eh, em = map(int, value.get("end_time", "23:59").split(":"))
        return {
            "start_datetime": datetime(sd.year, sd.month, sd.day, sh, sm),
            "end_datetime": datetime(ed.year, ed.month, ed.day, eh, em),
        }

    def to_sql_clause(self, value: Any) -> Optional[tuple[str, dict]]:
        if not self.validate(value):
            return None
        dts = self.parse_datetimes(value)
        return (
            "detected_at BETWEEN :start_dt AND :end_dt",
            {
                "start_dt": dts["start_datetime"],
                "end_dt": dts["end_datetime"],
            },
        )
