"""
QueryBuilder — Dynamic SQL construction for detection tables.

Single Responsibility: compose complete parameterized queries from
filter dicts.  All clause-level logic (daterange, shift, IN, parsing)
lives in ``sql_clauses``.

Does NOT resolve table names or line IDs (see ``table_resolver``).

Usage::

    from new_app.services.data.query_builder import query_builder

    sql, params = query_builder.build_detection_query(
        table_name="detection_line_bolsa25kg",
        cleaned={"daterange": {...}, "area_ids": [1, 2]},
    )
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from new_app.services.data.sql_clauses import (
    apply_daterange,
    apply_filters,
    build_shift_clause,
    table_with_hint,
)

# Type alias for the (sql_string, bind_params) return
QueryResult = Tuple[str, Dict[str, Any]]


class QueryBuilder:
    """
    Constructs parameterized SQL for detection and downtime tables.

    Stateless — every method returns a fresh ``(sql, bind_params)`` tuple.
    Delegates clause construction to ``sql_clauses``.
    """

    DETECTION_COLUMNS = (
        "detection_id",
        "detected_at",
        "area_id",
        "product_id",
    )

    DEFAULT_BATCH_SIZE = 500_000

    # ─────────────────────────────────────────────────────────────
    #  DETECTION QUERIES
    # ─────────────────────────────────────────────────────────────

    def build_detection_query(
        self,
        table_name: str,
        cleaned: Dict[str, Any],
        cursor_id: int = 0,
        limit: int = DEFAULT_BATCH_SIZE,
        partition_hint: str = "",
    ) -> QueryResult:
        """
        Build a paginated SELECT for a single detection table.
        """
        cols = ", ".join(self.DETECTION_COLUMNS)
        table_ref = table_with_hint(table_name, partition_hint)

        sql = f"SELECT {cols} FROM {table_ref} WHERE detection_id > :cursor_id"
        params: Dict[str, Any] = {"cursor_id": cursor_id}

        sql = apply_filters(sql, params, cleaned)
        sql += f" ORDER BY detection_id LIMIT {int(limit)}"

        return sql, params

    def build_detection_count_query(
        self,
        table_name: str,
        cleaned: Dict[str, Any],
        partition_hint: str = "",
    ) -> QueryResult:
        """
        Build a COUNT(*) query with the same filters as detection.
        """
        table_ref = table_with_hint(table_name, partition_hint)

        sql = f"SELECT COUNT(*) AS total FROM {table_ref} WHERE 1=1"
        params: Dict[str, Any] = {}

        sql = apply_filters(sql, params, cleaned)

        return sql, params

    def build_aggregation_query(
        self,
        table_name: str,
        cleaned: Dict[str, Any],
        group_column: str,
        agg_func: str = "COUNT",
        agg_column: str = "*",
        partition_hint: str = "",
    ) -> QueryResult:
        """
        Build a GROUP BY aggregation query.

        Example::

            query_builder.build_aggregation_query(
                "detection_line_bolsa25kg", cleaned, group_column="area_id",
            )
            # → SELECT area_id, COUNT(*) AS value FROM ... GROUP BY area_id
        """
        table_ref = table_with_hint(table_name, partition_hint)
        agg_expr = f"{agg_func}({agg_column})"

        sql = (
            f"SELECT {group_column}, {agg_expr} AS value "
            f"FROM {table_ref} WHERE 1=1"
        )
        params: Dict[str, Any] = {}

        sql = apply_filters(sql, params, cleaned)
        sql += f" GROUP BY {group_column}"

        return sql, params

    # ─────────────────────────────────────────────────────────────
    #  DOWNTIME QUERIES (prepared for Etapa 4)
    # ─────────────────────────────────────────────────────────────

    def build_downtime_query(
        self,
        table_name: str,
        cleaned: Dict[str, Any],
        cursor_id: int = 0,
        limit: int = 10_000,
    ) -> QueryResult:
        """
        Build a paginated SELECT for a downtime_events table.

        Uses ``start_time`` instead of ``detected_at`` for filtering.
        """
        sql = (
            "SELECT event_id, last_detection_id, start_time, end_time, "
            "duration_seconds, reason_code, reason, is_manual, created_at "
            f"FROM {table_name} WHERE event_id > :cursor_id"
        )
        params: Dict[str, Any] = {"cursor_id": cursor_id}

        sql = apply_daterange(sql, params, cleaned, time_column="start_time")

        shift = build_shift_clause(cleaned, params, time_column="start_time")
        if shift:
            sql += f" AND {shift}"

        sql += f" ORDER BY event_id LIMIT {int(limit)}"

        return sql, params


# ── Singleton ────────────────────────────────────────────────────
query_builder = QueryBuilder()
