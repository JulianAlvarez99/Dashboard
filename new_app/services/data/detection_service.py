"""
DetectionService — Thin orchestrator for the data extraction pipeline.

Single Responsibility: coordinate the extraction pipeline steps.
Delegates each concern to its specialized module:

  - Line resolution    → ``line_resolver``
  - Partition hints    → ``partition_manager``
  - Raw data fetching  → ``detection_repository``
  - Enrichment         → ``enrichment``
  - Export             → ``export``

This is the **public entry point** for all detection data access.
The resulting DataFrame is the single source of truth consumed by
all widget processors downstream.

Usage::

    from new_app.services.data.detection_service import detection_service

    async with db_manager.get_tenant_session_by_name(db_name) as session:
        df = await detection_service.get_enriched_detections(
            session=session,
            line_ids=[1, 2, 3],
            cleaned={"daterange": {...}, "shift_id": 1, ...},
        )
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List

import pandas as pd

from new_app.services.data.detection_repository import detection_repository
from new_app.services.data.enrichment import enrich_detections
from new_app.services.data.line_resolver import line_resolver
from new_app.services.data.partition_manager import partition_manager
from new_app.services.data.table_resolver import table_resolver

logger = logging.getLogger(__name__)


class DetectionService:
    """
    High-level orchestrator for the Etapa 3 pipeline.

    Each public method follows the same pattern:
      1. Resolve partition hints from daterange.
      2. Delegate to repository for raw data.
      3. Delegate to enrichment for metadata columns.
    """

    # ─────────────────────────────────────────────────────────────
    #  PUBLIC API
    # ─────────────────────────────────────────────────────────────

    async def get_enriched_detections(
        self,
        session,
        line_ids: List[int],
        cleaned: Dict[str, Any],
        use_partition_hints: bool = True,
    ) -> pd.DataFrame:
        """
        Full pipeline: query → enrich → return master DataFrame.

        Args:
            session:               Active async DB session (tenant).
            line_ids:              Production lines to query.
            cleaned:               Validated filter params from FilterEngine.
            use_partition_hints:   Generate PARTITION hints from daterange.

        Returns:
            Enriched DataFrame with metadata columns.
            Empty DataFrame if no data is found.
        """
        if not line_ids:
            return pd.DataFrame()

        hint = self._resolve_partition_hint(cleaned) if use_partition_hints else ""

        raw_df = await detection_repository.fetch_detections_multi_line(
            session=session,
            line_ids=line_ids,
            cleaned=cleaned,
            partition_hint=hint,
        )

        if raw_df.empty:
            logger.info("[DetectionService] No detections found for given filters")
            return pd.DataFrame()

        enriched = enrich_detections(raw_df)

        logger.info(
            f"[DetectionService] Enriched {len(enriched)} detections "
            f"for {len(line_ids)} lines"
        )
        return enriched

    async def get_detection_count(
        self,
        session,
        line_ids: List[int],
        cleaned: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Return detection counts per line without fetching all rows.

        Returns dict: ``{"total": N, "per_line": {line_id: count, ...}}``
        """
        counts: Dict[int, int] = {}
        total = 0

        for line_id in line_ids:
            table_name = table_resolver.detection_table(line_id)
            if not table_name:
                continue
            count = await detection_repository.count_detections(
                session=session,
                table_name=table_name,
                cleaned=cleaned,
            )
            counts[line_id] = count
            total += count

        return {"total": total, "per_line": counts}

    async def get_detection_summary(
        self,
        session,
        line_ids: List[int],
        cleaned: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Return a summary with counts grouped by area_type.

        Returns: ``{"total": N, "by_area_type": {"input": X, "output": Y}}``
        """
        df = await self.get_enriched_detections(session, line_ids, cleaned)
        if df.empty:
            return {"total": 0, "by_area_type": {}}

        by_type = {}
        if "area_type" in df.columns:
            by_type = df.groupby("area_type").size().to_dict()

        return {
            "total": len(df),
            "by_area_type": by_type,
            "lines_queried": line_ids,
        }

    # ─────────────────────────────────────────────────────────────
    #  PARTITION HINT HELPER
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_partition_hint(cleaned: Dict[str, Any]) -> str:
        """Generate a PARTITION hint from the daterange filter."""
        daterange = cleaned.get("daterange")
        if not daterange or not isinstance(daterange, dict):
            return ""

        sd = daterange.get("start_date")
        ed = daterange.get("end_date")
        if not sd or not ed:
            return ""

        try:
            start = date.fromisoformat(sd)
            end = date.fromisoformat(ed)
        except (ValueError, TypeError):
            return ""

        return partition_manager.get_partition_hint(start, end)


# ── Singleton ────────────────────────────────────────────────────
detection_service = DetectionService()
