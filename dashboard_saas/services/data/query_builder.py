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
QueryResult = Tuple[str, Dict[str, Any]]


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
        params: Dict[str, Any],
    ) -> QueryResult:
        """
        Build a SELECT for a detection table.

        Args:
            table_name: e.g. "detection_line_bolsa25kg"
            clauses: list of WHERE clause strings
            params: merged bind parameters

        Returns:
            (sql, params) ready for execution with SQLAlchemy text().
        """
        cols = ", ".join(self.DETECTION_COLUMNS)
        sql = f"SELECT {cols} FROM {table_name} WHERE 1=1"

        # Append all filter clauses
        for clause in clauses:
            sql += f" AND {clause}"

        sql += " ORDER BY detected_at"

        logger.debug("Built query: %s | params: %s", sql, params)
        return sql, params

    def build_count_query(
        self,
        table_name: str,
        clauses: List[str],
        params: Dict[str, Any],
    ) -> QueryResult:
        """Build a COUNT(*) query with the same filters."""
        sql = f"SELECT COUNT(*) AS total FROM {table_name} WHERE 1=1"

        for clause in clauses:
            sql += f" AND {clause}"

        return sql, params

    # ── Table resolution ────────────────────────────────────────

    @staticmethod
    def resolve_table_names(line_value: Any, line_options: list) -> List[str]:
        """
        Resolve detection table name(s) from the selected line value.

        Detection tables follow the pattern: detection_line_{line_name_lowercase}
        Example: line_name "Linea_1" → "detection_line_linea_1"

        Args:
            line_value: The value from the ProductionLineFilter
            line_options: The filter options to look up line metadata

        Returns:
            List of table names to query (one per line).
        """
        # Find the matching option
        opt = next(
            (o for o in line_options
             if o.get("value") == line_value or str(o.get("value")) == str(line_value)),
            None,
        )

        if not opt:
            logger.warning("No matching option for line value: %s", line_value)
            return []

        extra = opt.get("extra", {})

        # Group → multiple tables (iterate all line_ids and look up line_name)
        if extra.get("is_group"):
            line_ids = extra.get("line_ids", [])
            tables = []
            lines = metadata_cache.get_production_lines()
            for lid in line_ids:
                line = lines.get(lid)
                if line:
                    table = f"detection_line_{line['line_name'].lower()}"
                    tables.append(table)
            return tables

        # Single line → one table (use line_name from extra)
        line_name = extra.get("line_name")
        if line_name:
            return [f"detection_line_{line_name.lower()}"]

        # Fallback: look up from cache by line_id
        lines = metadata_cache.get_production_lines()
        for lid, data in lines.items():
            if lid == line_value or str(lid) == str(line_value):
                return [f"detection_line_{data['line_name'].lower()}"]

        return []


# ── Singleton ────────────────────────────────────────────────────
query_builder = QueryBuilder()
