"""
Unit tests for FilterEngine.validate_input().

Tests validation logic without requiring a live DB connection.
Uses mock filters to avoid dependency on MetadataCache.
"""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from new_app.services.filters.base import BaseFilter, FilterConfig


# ── Synthetic filter subclasses for testing ──────────────────────

class _AlwaysValidFilter(BaseFilter):
    """Filter that accepts any non-None value."""
    filter_type = "text"
    param_name = "always_valid"
    options_source = None
    default_value = "default"
    placeholder = None
    required = False
    depends_on = None
    ui_config = {}

    def validate(self, value: Any) -> bool:
        return value is not None

    def get_default(self):
        return self.default_value


class _FailingFilter(BaseFilter):
    """Filter that always rejects the provided value."""
    filter_type = "text"
    param_name = "failing"
    options_source = None
    default_value = None
    placeholder = None
    required = True
    depends_on = None
    ui_config = {}

    def validate(self, value: Any) -> bool:
        return False  # always invalid

    def get_default(self):
        return None


# ── Helper to build FilterConfig ────────────────────────────────

def _cfg(filter_id: int, class_name: str, param_name: str, required: bool = False):
    return FilterConfig(
        filter_id=filter_id,
        class_name=class_name,
        filter_type="text",
        param_name=param_name,
        display_order=filter_id,
        description="",
        placeholder=None,
        default_value=None,
        required=required,
        options_source=None,
        depends_on=None,
        ui_config={},
    )


# ── Tests ────────────────────────────────────────────────────────

def test_validate_input_passes_valid_value():
    """Valid value for the filter passes validation and is in cleaned."""
    cfg = _cfg(1, "_AlwaysValidFilter", "always_valid")
    f = _AlwaysValidFilter(cfg)

    with patch(
        "new_app.services.filters.engine.filter_engine.get_all",
        return_value=[f],
    ):
        from new_app.services.filters.engine import filter_engine

        result = filter_engine.validate_input({"always_valid": "hello"})

    assert result["valid"] is True
    assert result["cleaned"]["always_valid"] == "hello"
    assert result["errors"] == {}


def test_validate_input_invalid_value_produces_error():
    """Invalid value is collected in errors dict."""
    cfg = _cfg(1, "_FailingFilter", "failing", required=True)
    f = _FailingFilter(cfg)

    with patch(
        "new_app.services.filters.engine.filter_engine.get_all",
        return_value=[f],
    ):
        from new_app.services.filters.engine import filter_engine

        result = filter_engine.validate_input({"failing": "anything"})

    assert result["valid"] is False
    assert "failing" in result["errors"]


def test_validate_input_uses_default_when_not_provided():
    """Missing parameter uses the filter's default value."""
    cfg = _cfg(1, "_AlwaysValidFilter", "always_valid")
    f = _AlwaysValidFilter(cfg)

    with patch(
        "new_app.services.filters.engine.filter_engine.get_all",
        return_value=[f],
    ):
        from new_app.services.filters.engine import filter_engine

        result = filter_engine.validate_input({})  # no param provided

    # Default is "default" which passes _AlwaysValidFilter.validate()
    assert result["cleaned"]["always_valid"] == "default"


def test_date_range_filter_validates_valid_range():
    """DateRangeFilter accepts a proper date range."""
    from new_app.services.filters.types.date_range_filter import DateRangeFilter

    cfg = _cfg(1, "DateRangeFilter", "daterange", required=True)
    # Inject required fields that FilterConfig validator might need
    cfg.filter_type = "daterange"
    cfg.ui_config = {"show_time": True, "default_start_time": "00:00", "default_end_time": "23:59"}
    f = DateRangeFilter(cfg)

    valid = f.validate({
        "start_date": "2025-01-01",
        "end_date": "2025-01-31",
        "start_time": "08:00",
        "end_time": "17:00",
    })
    assert valid is True


def test_date_range_filter_rejects_inverted_range():
    """DateRangeFilter rejects start > end."""
    from new_app.services.filters.types.date_range_filter import DateRangeFilter

    cfg = _cfg(1, "DateRangeFilter", "daterange", required=True)
    cfg.filter_type = "daterange"
    cfg.ui_config = {"show_time": True, "default_start_time": "00:00", "default_end_time": "23:59"}
    f = DateRangeFilter(cfg)

    valid = f.validate({
        "start_date": "2025-02-01",
        "end_date": "2025-01-01",  # before start
    })
    assert valid is False


def test_date_range_filter_rejects_inverted_time_same_day():
    """DateRangeFilter rejects start_time > end_time when same day."""
    from new_app.services.filters.types.date_range_filter import DateRangeFilter

    cfg = _cfg(1, "DateRangeFilter", "daterange", required=True)
    cfg.filter_type = "daterange"
    cfg.ui_config = {"show_time": True, "default_start_time": "00:00", "default_end_time": "23:59"}
    f = DateRangeFilter(cfg)

    valid = f.validate({
        "start_date": "2025-01-01",
        "end_date": "2025-01-01",
        "start_time": "17:00",
        "end_time": "08:00",  # before start
    })
    assert valid is False
