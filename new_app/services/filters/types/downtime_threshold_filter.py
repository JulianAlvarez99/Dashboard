"""DowntimeThresholdFilter — Auto-discovery wrapper with class attributes."""

from __future__ import annotations

from new_app.services.filters.types.number import NumberFilter


class DowntimeThresholdFilter(NumberFilter):
    """Numeric downtime threshold (seconds) — applied in Python, not SQL."""

    filter_type    = "number"
    param_name     = "downtime_threshold"
    options_source = None
    default_value  = 10
    placeholder    = "Segundos"
    required       = False
    depends_on     = "line_id"
    ui_config      = {"min": 0, "step": 10, "unit": "s"}
