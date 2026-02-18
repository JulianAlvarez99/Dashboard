"""
DetectionRepository — Executes detection queries with cursor-based pagination.

Handles the low-level interaction with the MySQL detection_line_{name}
tables.  Returns raw ``pd.DataFrame`` instances — enrichment happens
in ``DetectionService``.

The cursor-based pagination avoids OFFSET and guarantees stable ordering
even on tables with millions of rows across multiple partitions.

Usage::

    repo = DetectionRepository()
    async with db_manager.get_tenant_session_by_name(db_name) as session:
        df = await repo.fetch_detections(
            session=session,
            table_name="detection_line_bolsa25kg",
            cleaned={"daterange": {...}, "area_ids": [1]},
        )
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from new_app.services.data.query_builder import query_builder, QueryBuilder
from new_app.services.data.table_resolver import table_resolver

logger = logging.getLogger(__name__)


class DetectionRepository:
    """
    Executes detection queries built by :class:`QueryBuilder`.

    All methods return raw DataFrames with the DB-native column names.
    No metadata enrichment occurs here (SRP separation).
    """

    # Safety cap: absolute maximum rows across all pagination batches
    MAX_TOTAL_ROWS = 2_000_000

    # Rows per batch (matches QueryBuilder.DEFAULT_BATCH_SIZE)
    BATCH_SIZE = QueryBuilder.DEFAULT_BATCH_SIZE

    # ─────────────────────────────────────────────────────────────
    #  DETECTION FETCHING
    # ─────────────────────────────────────────────────────────────

    async def fetch_detections(
        self,
        session: AsyncSession,
        table_name: str,
        cleaned: Dict[str, Any],
        partition_hint: str = "",
        max_rows: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Fetch raw detection data from a single table with pagination.

        Uses cursor-based pagination (``detection_id > :cursor_id``)
        to iterate over the table in batches of ``BATCH_SIZE``.

        Args:
            session:         Active async DB session.
            table_name:      ``detection_line_{line_name}``
            cleaned:         Validated filter params from FilterEngine.
            partition_hint:  Optional ``PARTITION (...)`` clause.
            max_rows:        Safety cap (defaults to ``MAX_TOTAL_ROWS``).

        Returns:
            DataFrame with columns: detection_id, detected_at, area_id, product_id.
            Empty DataFrame if the table doesn't exist or has no matching rows.
        """
        cap = max_rows or self.MAX_TOTAL_ROWS
        all_frames: List[pd.DataFrame] = []
        cursor_id = 0
        total_fetched = 0

        while total_fetched < cap:
            remaining = cap - total_fetched
            batch_limit = min(self.BATCH_SIZE, remaining)

            sql, params = query_builder.build_detection_query(
                table_name=table_name,
                cleaned=cleaned,
                cursor_id=cursor_id,
                limit=batch_limit,
                partition_hint=partition_hint,
            )

            try:
                result = await session.execute(text(sql), params)
                rows = result.mappings().all()
            except Exception as exc:
                # Table might not exist or be inaccessible
                logger.error(
                    f"[DetectionRepo] Error querying {table_name}: {exc}"
                )
                break

            if not rows:
                break

            batch_df = pd.DataFrame([dict(r) for r in rows])
            all_frames.append(batch_df)

            cursor_id = int(batch_df["detection_id"].max())
            total_fetched += len(rows)

            logger.debug(
                f"[DetectionRepo] {table_name}: batch={len(rows)}, "
                f"total={total_fetched}, cursor={cursor_id}"
            )

            # If we got fewer rows than requested, this is the last batch
            if len(rows) < batch_limit:
                break

        if not all_frames:
            return pd.DataFrame()

        combined = pd.concat(all_frames, ignore_index=True)
        logger.info(
            f"[DetectionRepo] {table_name}: {len(combined)} total rows fetched"
        )
        return combined

    async def fetch_detections_multi_line(
        self,
        session: AsyncSession,
        line_ids: List[int],
        cleaned: Dict[str, Any],
        partition_hint: str = "",
    ) -> pd.DataFrame:
        """
        Fetch detections for multiple production lines and concatenate.

        Adds a ``line_id`` column to each batch so processors can
        differentiate by production line.

        Args:
            session:         Active async DB session.
            line_ids:        List of production line IDs to query.
            cleaned:         Validated filter params from FilterEngine.
            partition_hint:  Optional ``PARTITION (...)`` clause.

        Returns:
            Combined DataFrame with ``line_id`` column added.
        """
        dataframes: List[pd.DataFrame] = []

        for line_id in line_ids:
            table_name = table_resolver.detection_table(line_id)
            if not table_name:
                logger.warning(
                    f"[DetectionRepo] No table name for line_id={line_id} "
                    "— line not in cache?"
                )
                continue

            df = await self.fetch_detections(
                session=session,
                table_name=table_name,
                cleaned=cleaned,
                partition_hint=partition_hint,
            )

            if not df.empty:
                df["line_id"] = line_id
                dataframes.append(df)

        if not dataframes:
            return pd.DataFrame()

        return pd.concat(dataframes, ignore_index=True)

    # ─────────────────────────────────────────────────────────────
    #  COUNT
    # ─────────────────────────────────────────────────────────────

    async def count_detections(
        self,
        session: AsyncSession,
        table_name: str,
        cleaned: Dict[str, Any],
        partition_hint: str = "",
    ) -> int:
        """
        Return the count of detections matching the filters.
        """
        sql, params = query_builder.build_detection_count_query(
            table_name=table_name,
            cleaned=cleaned,
            partition_hint=partition_hint,
        )
        try:
            result = await session.execute(text(sql), params)
            row = result.first()
            return row[0] if row else 0
        except Exception as exc:
            logger.error(f"[DetectionRepo] Count error on {table_name}: {exc}")
            return 0

    # ─────────────────────────────────────────────────────────────
    #  AGGREGATION
    # ─────────────────────────────────────────────────────────────

    async def fetch_aggregated(
        self,
        session: AsyncSession,
        table_name: str,
        cleaned: Dict[str, Any],
        group_column: str,
        agg_func: str = "COUNT",
        agg_column: str = "*",
        partition_hint: str = "",
    ) -> pd.DataFrame:
        """
        Fetch grouped/aggregated detection data.

        Returns a DataFrame with columns: ``[group_column, "value"]``.
        """
        sql, params = query_builder.build_aggregation_query(
            table_name=table_name,
            cleaned=cleaned,
            group_column=group_column,
            agg_func=agg_func,
            agg_column=agg_column,
            partition_hint=partition_hint,
        )
        try:
            result = await session.execute(text(sql), params)
            rows = result.mappings().all()
            if not rows:
                return pd.DataFrame()
            return pd.DataFrame([dict(r) for r in rows])
        except Exception as exc:
            logger.error(
                f"[DetectionRepo] Aggregation error on {table_name}: {exc}"
            )
            return pd.DataFrame()


# ── Singleton ────────────────────────────────────────────────────
detection_repository = DetectionRepository()
