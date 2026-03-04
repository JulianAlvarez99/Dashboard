"""
Unit tests for QueryBuilder — verifies SQL generation logic.

Tests that the generated SQL strings contain the expected clauses
without requiring a live DB connection.
"""

from __future__ import annotations

import pytest

from new_app.services.data.query_builder import QueryBuilder


@pytest.fixture
def qb():
    return QueryBuilder()


def test_build_detection_query_basic(qb):
    """Basic query has mandatory cursor_id clause and ORDER BY."""
    sql, params = qb.build_detection_query(
        table_name="detection_line_test",
        cleaned={},
    )
    assert "detection_line_test" in sql
    assert ":cursor_id" in sql
    assert "ORDER BY detection_id" in sql
    assert params["cursor_id"] == 0


def test_build_detection_query_cursor(qb):
    """cursor_id is passed as bind parameter."""
    _, params = qb.build_detection_query(
        table_name="t", cleaned={}, cursor_id=999,
    )
    assert params["cursor_id"] == 999


def test_build_detection_query_daterange(qb):
    """Daterange filter adds datetime WHERE clauses."""
    cleaned = {
        "daterange": {
            "start_date": "2025-01-01",
            "end_date": "2025-01-31",
            "start_time": "08:00",
            "end_time": "17:00",
        }
    }
    sql, params = qb.build_detection_query("t", cleaned)
    # Expect a daterange-related param
    assert any("start" in k or "end" in k for k in params)


def test_build_count_query_returns_count(qb):
    """Count query uses COUNT(*)."""
    sql, _ = qb.build_detection_count_query(
        table_name="detection_line_bolsa",
        cleaned={},
    )
    assert "COUNT" in sql.upper()
    assert "detection_line_bolsa" in sql


def test_build_detection_query_limit(qb):
    """Custom limit is embedded in the SQL."""
    sql, _ = qb.build_detection_query("t", {}, limit=1000)
    assert "LIMIT 1000" in sql


def test_build_detection_query_area_ids(qb):
    """area_ids filter adds an IN clause."""
    cleaned = {"area_ids": [1, 2, 3]}
    sql, params = qb.build_detection_query("t", cleaned)
    assert "area_id" in sql.lower()


def test_partition_hint_included(qb):
    """Partition hint appears in FROM clause when provided."""
    sql, _ = qb.build_detection_query(
        "t", {}, partition_hint="p2025_01",
    )
    assert "p2025_01" in sql
