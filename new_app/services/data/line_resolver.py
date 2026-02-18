"""
LineResolver — Resolve production line IDs from filter parameters.

Single Responsibility: interpret the ``line_id`` / ``line_ids`` keys
from the cleaned filter dict and return a concrete list of integer IDs.

Handles:
  - ``"all"``          → every active line from cache.
  - ``"group_X"``      → lines defined in a filter's ``additional_filter``.
  - ``"group_X_Y"``    → multi-group with index selection.
  - ``[1, 2, 3]``      → explicit list pass-through.
  - ``5``              → single integer line.
  - ``None``           → fallback to all active lines.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from new_app.core.cache import metadata_cache

logger = logging.getLogger(__name__)


class LineResolver:
    """
    Resolves a list of integer line IDs from filter parameters.
    """

    @staticmethod
    def resolve(cleaned: Dict[str, Any]) -> List[int]:
        """
        Extract line IDs from the cleaned filter dict.

        Priority:
          1. ``line_ids`` key (explicit list or CSV string).
          2. ``line_id`` key (``"all"``, ``"group_X"``, or integer).
          3. Fallback: all active lines from cache.

        Returns:
            List of integer line IDs (may be empty if cache is empty).
        """
        # ── Explicit line_ids list ───────────────────────────
        raw = cleaned.get("line_ids")
        if raw:
            if isinstance(raw, list):
                return [int(x) for x in raw]
            if isinstance(raw, str):
                return [int(x.strip()) for x in raw.split(",")]

        # ── Single line_id value ─────────────────────────────
        line_id = cleaned.get("line_id")
        if line_id is None:
            return metadata_cache.get_active_line_ids()

        if str(line_id) == "all":
            return metadata_cache.get_active_line_ids()

        if isinstance(line_id, str) and line_id.startswith("group_"):
            return LineResolver._resolve_group(line_id)

        try:
            return [int(line_id)]
        except (ValueError, TypeError):
            logger.warning(f"[LineResolver] Cannot parse line_id={line_id}")
            return metadata_cache.get_active_line_ids()

    # ─────────────────────────────────────────────────────────────
    #  GROUP RESOLUTION
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_group(group_value: str) -> List[int]:
        """
        Resolve a group value to line IDs from cached filter metadata.

        Format: ``group_{filter_id}`` or ``group_{filter_id}_{index}``.
        """
        parts = group_value.split("_")

        if len(parts) == 2:
            return LineResolver._resolve_single_group(parts)
        if len(parts) == 3:
            return LineResolver._resolve_indexed_group(parts)

        return metadata_cache.get_active_line_ids()

    @staticmethod
    def _resolve_single_group(parts: List[str]) -> List[int]:
        """Resolve ``group_{filter_id}`` → line_ids from additional_filter."""
        try:
            fid = int(parts[1])
        except ValueError:
            return metadata_cache.get_active_line_ids()

        af = LineResolver._parse_additional_filter(fid)
        if af and "line_ids" in af:
            return [int(x) for x in af["line_ids"]]

        return metadata_cache.get_active_line_ids()

    @staticmethod
    def _resolve_indexed_group(parts: List[str]) -> List[int]:
        """Resolve ``group_{filter_id}_{index}`` → specific group."""
        try:
            fid = int(parts[1])
            idx = int(parts[2])
        except ValueError:
            return metadata_cache.get_active_line_ids()

        af = LineResolver._parse_additional_filter(fid)
        if af and "groups" in af:
            groups = af["groups"]
            if 0 <= idx < len(groups):
                return [int(x) for x in groups[idx]["line_ids"]]

        return metadata_cache.get_active_line_ids()

    @staticmethod
    def _parse_additional_filter(filter_id: int) -> dict | None:
        """
        Parse the ``additional_filter`` JSON from a cached filter row.

        Centralizes the JSON parsing that was previously duplicated.
        """
        filters = metadata_cache.get_filters()
        fdata = filters.get(filter_id, {})
        af = fdata.get("additional_filter")

        if af is None:
            return None
        if isinstance(af, str):
            try:
                return json.loads(af)
            except (json.JSONDecodeError, TypeError):
                return None
        if isinstance(af, dict):
            return af

        return None


# ── Singleton ────────────────────────────────────────────────────
line_resolver = LineResolver()
