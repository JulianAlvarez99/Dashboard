"""
QueryBuilder — Assembles SQL queries from filter clauses.

Simple and concrete:
1. FilterEngine collects all (clause, params) from active filters.
2. QueryBuilder receives those clauses and builds the final query.
3. The table name is resolved dynamically from the line_code.

Phase 3: Detection queries only. Downtime queries in future phases.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from dashboard_saas.core.cache import metadata_cache

logger = logging.getLogger(__name__)

# Type alias for (sql_string, bind_params)
QueryResult = Tuple[str]


class QueryBuilder:
    """
    Builds parameterized SQL from filter clauses.

    Usage:
        clauses = [("line_id = :line_id", {"line_id": 3}),
                   ("detected_at BETWEEN :start_dt AND :end_dt", {...})]
        sql, params = qb.build_detection_query("detection_line_bolsa25kg", clauses)
    """

    # Columns to SELECT from detection tables
    DETECTION_COLUMNS = (
        "detection_id",
        "detected_at",
        "area_id",
        "product_id",
    )

    def build_detection_query(
        self,
        table_name: str,
        clauses: List[str],
    ) -> QueryResult:
        """
        Build a SELECT for a detection table.

        Args:
            table_name: e.g. "detection_line_bolsa25kg"
            clauses: list of WHERE clause strings

        Returns:
            (sql, params) ready for execution with SQLAlchemy text().
        """
        cols = ", ".join(self.DETECTION_COLUMNS)
        sql = f"SELECT {cols} FROM {table_name} WHERE 1=1"

        # Append all filter clauses
        for clause in clauses:
            sql += f" AND {clause}"

        sql += " ORDER BY detected_at"

        logger.debug("Built query: %s", sql)
        return sql

    def build_count_query(
        self,
        table_name: str,
        clauses: List[str],
    ) -> QueryResult:
        """Build a COUNT(*) query with the same filters."""
        sql = f"SELECT COUNT(*) AS total FROM {table_name} WHERE 1=1"

        for clause in clauses:
            sql += f" AND {clause}"

        return sql


# ── Singleton ────────────────────────────────────────────────────
query_builder = QueryBuilder()
