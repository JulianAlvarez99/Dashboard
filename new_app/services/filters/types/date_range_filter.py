"""DateRangeFilter — Auto-discovery wrapper with class attributes."""

from __future__ import annotations

from new_app.services.filters.types.daterange import DateRangeFilter as _Base


class DateRangeFilter(_Base):
    """Date + optional time range selector."""

    filter_type    = "daterange"
    param_name     = "daterange"
    options_source = None
    default_value  = None
    placeholder    = None
    required       = True
    depends_on     = None
    ui_config      = {
        "show_time": True,
        "default_start_time": "00:00",
        "default_end_time": "23:59",
    }
