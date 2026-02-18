"""
DowntimeService — Orchestrator for the downtime data pipeline.

Single Responsibility: coordinate all downtime-related steps:
  1. Fetch DB-recorded downtime events (from ``downtime_events_{line}``).
  2. Calculate gap-based downtimes from detection timestamps.
  3. De-duplicate (DB wins over calculated when overlapping).
  4. Merge, normalize, and enrich with line metadata.

This is the public entry point for all downtime data access.

Usage::

    from new_app.services.data.downtime_service import downtime_service

    async with db_manager.get_tenant_session_by_name(db_name) as session:
        downtime_df = await downtime_service.get_downtime(
            session=session,
            line_ids=[1, 2],
            cleaned={...},
            detections_df=master_df,  # for gap calculation
        )
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from new_app.core.cache import metadata_cache
from new_app.services.data.downtime_calculator import (
    calculate_gap_downtimes,
    remove_overlapping,
)
from new_app.services.data.downtime_repository import downtime_repository

logger = logging.getLogger(__name__)


class DowntimeService:
    """
    High-level orchestrator for the downtime pipeline.

    Output DataFrame columns (normalized):
        start_time, end_time, duration, reason_code, line_id,
        line_name, source, is_manual
    """

    async def get_downtime(
        self,
        session,
        line_ids: List[int],
        cleaned: Dict[str, Any],
        detections_df: Optional[pd.DataFrame] = None,
        threshold_override: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Full downtime pipeline:
          1. Fetch DB events.
          2. Calculate gap-based events from detections.
          3. Remove overlaps (DB wins).
          4. Merge and enrich.

        Args:
            session:           Active async DB session (tenant).
            line_ids:          Production lines to process.
            cleaned:           Validated filter params.
            detections_df:     Master detections DataFrame for gap calc.
            threshold_override: Override per-line downtime threshold (seconds).

        Returns:
            Unified downtime DataFrame, enriched with line_name.
        """
        # Step 1: DB-recorded events
        db_df = await self._fetch_db_events(session, line_ids, cleaned)

        # Step 2: Gap-calculated events
        calc_df = self._calculate_gap_events(
            detections_df, line_ids, threshold_override,
        )

        # Step 3: De-duplicate
        if not calc_df.empty and not db_df.empty:
            calc_df = remove_overlapping(calc_df, db_df)

        # Step 4: Merge and enrich
        merged = self._merge_and_enrich(db_df, calc_df)

        logger.info(
            f"[DowntimeService] {len(merged)} total downtime events "
            f"(DB: {len(db_df)}, calculated: {len(calc_df)})"
        )
        return merged

    async def get_db_downtime_only(
        self,
        session,
        line_ids: List[int],
        cleaned: Dict[str, Any],
    ) -> pd.DataFrame:
        """Fetch only DB-recorded events (no gap calculation)."""
        db_df = await self._fetch_db_events(session, line_ids, cleaned)
        return self._enrich(db_df)

    # ─────────────────────────────────────────────────────────────
    #  INTERNAL STEPS
    # ─────────────────────────────────────────────────────────────

    async def _fetch_db_events(
        self,
        session,
        line_ids: List[int],
        cleaned: Dict[str, Any],
    ) -> pd.DataFrame:
        """Step 1: Fetch from downtime_events tables."""
        db_df = await downtime_repository.fetch_downtime_multi_line(
            session=session,
            line_ids=line_ids,
            cleaned=cleaned,
        )

        if db_df.empty:
            return pd.DataFrame()

        # Normalize DB columns
        db_df = self._normalize_db_columns(db_df)
        return db_df

    @staticmethod
    def _calculate_gap_events(
        detections_df: Optional[pd.DataFrame],
        line_ids: List[int],
        threshold_override: Optional[int],
    ) -> pd.DataFrame:
        """Step 2: Gap-based calculation from detection timestamps."""
        if detections_df is None or detections_df.empty:
            return pd.DataFrame()

        return calculate_gap_downtimes(
            detections_df, line_ids, threshold_override,
        )

    def _merge_and_enrich(
        self,
        db_df: pd.DataFrame,
        calc_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Step 4: Concatenate DB + calculated, enrich, sort."""
        frames = [f for f in [db_df, calc_df] if not f.empty]
        if not frames:
            return pd.DataFrame()

        merged = pd.concat(frames, ignore_index=True)

        # Ensure datetime types
        for col in ("start_time", "end_time"):
            if col in merged.columns:
                merged[col] = pd.to_datetime(merged[col])

        # Sort by start_time
        if "start_time" in merged.columns:
            merged = merged.sort_values("start_time").reset_index(drop=True)

        return self._enrich(merged)

    @staticmethod
    def _normalize_db_columns(df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize DB downtime columns to match the unified schema.

        DB has ``duration_seconds`` → we rename to ``duration``.
        DB has ``is_manual`` → keep as-is.
        """
        rename_map = {}
        if "duration_seconds" in df.columns:
            rename_map["duration_seconds"] = "duration"

        if rename_map:
            df = df.rename(columns=rename_map)

        # Add source marker if not present
        if "source" not in df.columns:
            df["source"] = "db"

        return df

    @staticmethod
    def _enrich(df: pd.DataFrame) -> pd.DataFrame:
        """
        Add line metadata columns from cache.

        Adds ``line_name`` based on ``line_id``.
        Ensures ``duration`` is in seconds (float).
        """
        if df.empty:
            return df

        # Add line_name from cache
        if "line_id" in df.columns:
            lines = metadata_cache.get_production_lines()
            df["line_name"] = df["line_id"].map(
                lambda lid: lines.get(lid, {}).get("line_name", f"Line {lid}")
            )

        # Ensure duration is float seconds
        if "duration" in df.columns:
            df["duration"] = pd.to_numeric(df["duration"], errors="coerce").fillna(0)

        return df


# ── Singleton ────────────────────────────────────────────────────
downtime_service = DowntimeService()
