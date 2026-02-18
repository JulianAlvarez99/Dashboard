"""
PartitionManager — Monthly RANGE partitioning for detection & downtime tables.

MySQL RANGE partitioning on ``YEAR(detected_at) * 100 + MONTH(detected_at)``
allows the query engine to prune months outside the user's selected date range,
dramatically reducing I/O on tables with tens of millions of rows.

Responsibilities:
  - Ensure partitions exist ahead of time (default: 3 months forward).
  - Create new monthly partitions by REORGANIZE PARTITION pmax.
  - Remove old partitions beyond a retention window.
  - Generate PARTITION hints for the QueryBuilder.

Design:
  The app *consumes* the database — it does NOT create the tables.
  Tables (detection_line_X, downtime_events_X) already exist.
  This manager only adds/removes/lists partitions on existing tables.

Usage::

    pm = PartitionManager()
    async with db_manager.get_tenant_session_by_name(db_name) as session:
        await pm.ensure_partitions(session, "detection_line_bolsa25kg")
        hint = pm.get_partition_hint(date(2026, 1, 1), date(2026, 2, 15))
        # → "PARTITION (p202601, p202602)"
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class PartitionManager:
    """
    Manages monthly RANGE partitions on detection / downtime tables.

    Partition naming convention:
      ``p{YYYYMM}``  e.g. ``p202601``, ``p202602``
      Plus a catch-all ``pmax`` with ``VALUES LESS THAN MAXVALUE``.
    """

    # ─────────────────────────────────────────────────────────────
    #  INSPECTION
    # ─────────────────────────────────────────────────────────────

    async def get_existing_partitions(
        self,
        session: AsyncSession,
        table_name: str,
    ) -> List[str]:
        """
        Return the names of all partitions on *table_name*.

        Uses ``INFORMATION_SCHEMA.PARTITIONS``.  Returns an empty list
        if the table is not partitioned or does not exist.
        """
        sql = """
            SELECT PARTITION_NAME
            FROM INFORMATION_SCHEMA.PARTITIONS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = :table_name
              AND PARTITION_NAME IS NOT NULL
            ORDER BY PARTITION_ORDINAL_POSITION
        """
        result = await session.execute(text(sql), {"table_name": table_name})
        return [row[0] for row in result.fetchall()]

    async def is_partitioned(
        self,
        session: AsyncSession,
        table_name: str,
    ) -> bool:
        """Check whether *table_name* has any partitions."""
        parts = await self.get_existing_partitions(session, table_name)
        return len(parts) > 0

    # ─────────────────────────────────────────────────────────────
    #  ENSURE PARTITIONS
    # ─────────────────────────────────────────────────────────────

    async def ensure_partitions(
        self,
        session: AsyncSession,
        table_name: str,
        months_ahead: int = 3,
        reference_date: Optional[date] = None,
    ) -> List[str]:
        """
        Guarantee that partitions exist from the current month up to
        *months_ahead* months into the future.

        If the table is not yet partitioned, this is a no-op (the DBA
        must first ALTER TABLE to add RANGE partitioning).

        New partitions are created by REORGANIZE PARTITION pmax if the
        target partition does not already exist.

        Returns the names of newly created partitions (may be empty).
        """
        existing = await self.get_existing_partitions(session, table_name)
        if not existing:
            logger.warning(
                f"[Partition] {table_name} has no partitions — "
                "cannot ensure; DBA must partition the table first."
            )
            return []

        has_pmax = "pmax" in existing

        ref = reference_date or date.today()
        needed = self._partitions_for_range(ref, months_ahead)
        existing_set = set(existing)
        created: List[str] = []

        for part_name, boundary_value in needed:
            if part_name in existing_set:
                continue

            if has_pmax:
                await self._reorganize_pmax(
                    session, table_name, part_name, boundary_value
                )
            else:
                await self._add_partition(
                    session, table_name, part_name, boundary_value
                )
            created.append(part_name)
            logger.info(f"[Partition] Created {part_name} on {table_name}")

        return created

    # ─────────────────────────────────────────────────────────────
    #  CLEANUP
    # ─────────────────────────────────────────────────────────────

    async def drop_old_partitions(
        self,
        session: AsyncSession,
        table_name: str,
        retention_months: int = 24,
        reference_date: Optional[date] = None,
    ) -> List[str]:
        """
        Drop partitions older than *retention_months*.

        Returns the names of dropped partitions.
        """
        ref = reference_date or date.today()
        cutoff_value = (ref.year * 100 + ref.month) - retention_months
        # Normalize: if month overflows, fix year
        cutoff_year = cutoff_value // 100
        cutoff_month = cutoff_value % 100
        if cutoff_month <= 0:
            cutoff_year -= 1
            cutoff_month += 12
        cutoff = cutoff_year * 100 + cutoff_month

        existing = await self.get_existing_partitions(session, table_name)
        dropped: List[str] = []

        for part_name in existing:
            if part_name == "pmax":
                continue
            # Extract YYYYMM from partition name (e.g. p202601 → 202601)
            try:
                yyyymm = int(part_name.lstrip("p"))
            except ValueError:
                continue
            if yyyymm < cutoff:
                await self._drop_partition(session, table_name, part_name)
                dropped.append(part_name)
                logger.info(
                    f"[Partition] Dropped {part_name} from {table_name} "
                    f"(older than {retention_months} months)"
                )

        return dropped

    # ─────────────────────────────────────────────────────────────
    #  PARTITION HINT (for QueryBuilder)
    # ─────────────────────────────────────────────────────────────

    def get_partition_hint(
        self,
        start_date: date,
        end_date: date,
    ) -> str:
        """
        Return a ``PARTITION (p202601, p202602, ...)`` clause that the
        QueryBuilder can inject right after the table name to enable
        **partition pruning** at the MySQL level.

        If the range spans more than 12 months, returns an empty string
        (let MySQL decide — the hint would be too long to be helpful).
        """
        partitions = self._partition_names_for_range(start_date, end_date)
        if not partitions or len(partitions) > 12:
            return ""
        return f"PARTITION ({', '.join(partitions)})"

    # ─────────────────────────────────────────────────────────────
    #  INTERNAL HELPERS
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def _partitions_for_range(
        ref: date, months_ahead: int
    ) -> List[Tuple[str, int]]:
        """
        Generate ``(partition_name, boundary_value)`` tuples from
        ``ref`` month forward.

        ``boundary_value`` is the ``YEAR*100+MONTH`` of the **next**
        month (LESS THAN semantics).
        """
        result: List[Tuple[str, int]] = []
        current = ref.replace(day=1)

        for _ in range(months_ahead + 1):  # +1 to include current month
            part_name = f"p{current.year}{current.month:02d}"
            # Boundary = next month
            nxt = (current + timedelta(days=32)).replace(day=1)
            boundary = nxt.year * 100 + nxt.month
            result.append((part_name, boundary))
            current = nxt

        return result

    @staticmethod
    def _partition_names_for_range(
        start_date: date, end_date: date
    ) -> List[str]:
        """Return partition names covering ``[start_date, end_date]``."""
        names: List[str] = []
        current = start_date.replace(day=1)
        while current <= end_date:
            names.append(f"p{current.year}{current.month:02d}")
            nxt = (current + timedelta(days=32)).replace(day=1)
            current = nxt
        return names

    async def _reorganize_pmax(
        self,
        session: AsyncSession,
        table_name: str,
        part_name: str,
        boundary_value: int,
    ) -> None:
        """
        Split ``pmax`` to create a new partition before it.

        ``ALTER TABLE t REORGANIZE PARTITION pmax INTO (
            PARTITION p202603 VALUES LESS THAN (202604),
            PARTITION pmax VALUES LESS THAN MAXVALUE
        )``
        """
        sql = f"""
            ALTER TABLE {table_name}
            REORGANIZE PARTITION pmax INTO (
                PARTITION {part_name} VALUES LESS THAN ({boundary_value}),
                PARTITION pmax VALUES LESS THAN MAXVALUE
            )
        """
        await session.execute(text(sql))
        await session.commit()

    async def _add_partition(
        self,
        session: AsyncSession,
        table_name: str,
        part_name: str,
        boundary_value: int,
    ) -> None:
        """Add a partition (when there is no pmax catch-all)."""
        sql = f"""
            ALTER TABLE {table_name}
            ADD PARTITION (
                PARTITION {part_name} VALUES LESS THAN ({boundary_value})
            )
        """
        await session.execute(text(sql))
        await session.commit()

    async def _drop_partition(
        self,
        session: AsyncSession,
        table_name: str,
        part_name: str,
    ) -> None:
        """Drop a single partition."""
        sql = f"ALTER TABLE {table_name} DROP PARTITION {part_name}"
        await session.execute(text(sql))
        await session.commit()


# ── Singleton ────────────────────────────────────────────────────
partition_manager = PartitionManager()
