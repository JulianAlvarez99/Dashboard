"""
DowntimeRepository — Cursor-paginated fetch from ``downtime_events_{line}`` tables.

Single Responsibility: execute downtime queries built by QueryBuilder.
Returns raw ``pd.DataFrame`` — enrichment is handled by ``downtime_service``.

Mirrors the pattern of DetectionRepository but targets downtime tables.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from new_app.services.data.query_builder import query_builder
from new_app.services.data.table_resolver import table_resolver

logger = logging.getLogger(__name__)


class DowntimeRepository:
    """
    Executes downtime queries with cursor-based pagination.

    Returns DataFrames with DB-native column names:
    ``event_id, last_detection_id, start_time, end_time,
    duration_seconds, reason_code, reason, is_manual, created_at``
    """

    MAX_TOTAL_ROWS = 100_000
    BATCH_SIZE = 10_000

    async def fetch_downtime(
        self,
        session: AsyncSession,
        table_name: str,
        cleaned: Dict[str, Any],
        max_rows: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Fetch downtime events from a single table with cursor pagination.
        """
        cap = max_rows or self.MAX_TOTAL_ROWS
        all_frames: List[pd.DataFrame] = []
        cursor_id = 0
        total_fetched = 0

        while total_fetched < cap:
            remaining = cap - total_fetched
            batch_limit = min(self.BATCH_SIZE, remaining)

            sql, params = query_builder.build_downtime_query(
                table_name=table_name,
                cleaned=cleaned,
                cursor_id=cursor_id,
                limit=batch_limit,
            )

            try:
                result = await session.execute(text(sql), params)
                rows = result.mappings().all()
            except Exception as exc:
                logger.error(
                    f"[DowntimeRepo] Error querying {table_name}: {exc}"
                )
                break

            if not rows:
                break

            batch_df = pd.DataFrame([dict(r) for r in rows])
            all_frames.append(batch_df)

            cursor_id = int(batch_df["event_id"].max())
            total_fetched += len(rows)

            if len(rows) < batch_limit:
                break

        if not all_frames:
            return pd.DataFrame()

        combined = pd.concat(all_frames, ignore_index=True)
        logger.info(
            f"[DowntimeRepo] {table_name}: {len(combined)} downtime events fetched"
        )
        return combined

    async def fetch_downtime_multi_line(
        self,
        session: AsyncSession,
        line_ids: List[int],
        cleaned: Dict[str, Any],
    ) -> pd.DataFrame:
        """
        Fetch downtime events from multiple lines and concatenate.

        Adds ``line_id`` column to each batch.
        """
        dataframes: List[pd.DataFrame] = []

        for line_id in line_ids:
            table_name = table_resolver.downtime_table(line_id)
            if not table_name:
                logger.warning(
                    f"[DowntimeRepo] No downtime table for line_id={line_id}"
                )
                continue

            df = await self.fetch_downtime(
                session=session,
                table_name=table_name,
                cleaned=cleaned,
            )

            if not df.empty:
                df["line_id"] = line_id
                dataframes.append(df)

        if not dataframes:
            return pd.DataFrame()

        return pd.concat(dataframes, ignore_index=True)


# ── Singleton ────────────────────────────────────────────────────
downtime_repository = DowntimeRepository()
