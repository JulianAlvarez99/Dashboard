"""
TableResolver — Resolve dynamic table names from production line metadata.

Single Responsibility: map line_id → table name via MetadataCache.

This module is consumed by QueryBuilder, DetectionRepository,
DetectionService, and API endpoints — centralizing the naming
convention in one place.

Convention:
  detection table → ``detection_line_{line_name.lower()}``
  downtime table  → ``downtime_events_{line_name.lower()}``
"""

from __future__ import annotations

import logging
from typing import Optional

from new_app.core.cache import metadata_cache

logger = logging.getLogger(__name__)


class TableResolver:
    """
    Resolves dynamic table names from cached production line metadata.
    """

    @staticmethod
    def detection_table(line_id: int) -> Optional[str]:
        """
        Resolve the detection table name for a production line.

        Returns ``detection_line_{line_name.lower()}`` or ``None``
        if the line is not found in cache.
        """
        line = metadata_cache.get_production_line(line_id)
        if not line:
            logger.warning(
                f"[TableResolver] line_id={line_id} not found in cache"
            )
            return None
        return f"detection_line_{line['line_name'].lower()}"

    @staticmethod
    def downtime_table(line_id: int) -> Optional[str]:
        """
        Resolve the downtime events table name for a production line.

        Returns ``downtime_events_{line_name.lower()}`` or ``None``
        if the line is not found in cache.
        """
        line = metadata_cache.get_production_line(line_id)
        if not line:
            logger.warning(
                f"[TableResolver] line_id={line_id} not found in cache"
            )
            return None
        return f"downtime_events_{line['line_name'].lower()}"


# ── Singleton ────────────────────────────────────────────────────
table_resolver = TableResolver()
