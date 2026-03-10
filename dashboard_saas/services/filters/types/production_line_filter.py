"""
ProductionLineFilter — Dropdown to select production line(s).

Supports:
- Individual line selection (line_id = :line_id)
- "All lines" shortcut (line_id IN :line_ids)
- Predefined groups from additional_filter in DB

SQL contribution:
    line_id = :line_id      (single line)
    line_id IN :line_ids    (group or "all")
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from dashboard_saas.core.cache import metadata_cache
from dashboard_saas.services.filters.base import BaseFilter, FilterOption

logger = logging.getLogger(__name__)


class ProductionLineFilter(BaseFilter):
    """Dropdown to select a production line (individual, all, or group)."""

    # ── Class attributes ─────────────────────────────────────────
    filter_type = "dropdown"
    param_name = "line_id"
    required = True
    placeholder = "Seleccionar línea"
    default_value = None
    ui_config = {"supports_groups": True}

    # ── Options ──────────────────────────────────────────────────

    def get_options(self) -> List[FilterOption]:
        """
        Build the list of options from cached production lines.

        Order: "All lines" → Groups (from additional_filter) → Individual lines.
        """
        lines = metadata_cache.get_production_lines()
        options: List[FilterOption] = []

        # 1. "Todas las líneas" when there's more than one line
        all_ids = list(lines.keys())
        if len(all_ids) > 1:
            options.append(FilterOption(
                value="all",
                label="Todas las líneas",
                extra={"is_group": True, "line_ids": all_ids},
            ))

        # 2. Groups from additional_filter in DB
        #    Scans the additional_filter column of the cached filter rows
        #    looking for group definitions like:
        #      {"alias": "Fraccionado", "line_ids": [2, 3, 4]}
        #      {"groups": [{"alias": "A", "line_ids": [1, 2]}, ...]}
        groups = self._parse_groups()
        options.extend(groups)

        # 3. Individual lines
        for line_id, data in lines.items():
            options.append(FilterOption(
                value=line_id,
                label=data["line_name"],
                extra={
                    "is_group": False,
                    "line_ids": None,
                    "line_name": data["line_name"],
                    "line_code": data["line_code"],
                    "downtime_threshold": data.get("downtime_threshold"),
                },
            ))

        return options

    def _parse_groups(self) -> List[FilterOption]:
        """
        Parse group definitions from additional_filter in the DB.

        Searches ALL cached filter rows for group definitions.
        """
        groups: List[FilterOption] = []
        filters = metadata_cache.get_filters()

        for fid, fdata in filters.items():
            af = fdata.get("additional_filter")
            if not af:
                continue

            # Parse JSON string if needed
            if isinstance(af, str):
                try:
                    af = json.loads(af)
                except (json.JSONDecodeError, TypeError):
                    continue

            if not isinstance(af, dict):
                continue

            # Single group: {"alias": "...", "line_ids": [...]}
            if "alias" in af and "line_ids" in af:
                groups.append(FilterOption(
                    value=f"group_{fid}",
                    label=af["alias"],
                    extra={"is_group": True, "line_ids": af["line_ids"]},
                ))

            # Multiple groups: {"groups": [{"alias": ..., "line_ids": ...}, ...]}
            elif "groups" in af:
                for idx, grp in enumerate(af["groups"]):
                    if "alias" in grp and "line_ids" in grp:
                        groups.append(FilterOption(
                            value=f"group_{fid}_{idx}",
                            label=grp["alias"],
                            extra={"is_group": True, "line_ids": grp["line_ids"]},
                        ))

        return groups

    # ── Validation ───────────────────────────────────────────────

    def validate(self, value: Any) -> bool:
        """Check that the value is a valid option."""
        if value is None or value == "":
            return not self.required
        # Check against available options
        opts = self.get_options()
        return any(
            o.value == value or str(o.value) == str(value)
            for o in opts
        )

    # ── Table Resolution ────────────────────────────────────────

    def get_target_tables(self, value: Any) -> List[str]:
        """
        Detection tables are partitioned by line: detection_line_{line_name}
        This filter determines WHICH tables are queried based on the line_id/group selected.
        """
        if value is None or value == "":
            return []

        opt = next(
            (o for o in self.get_options()
             if o.value == value or str(o.value) == str(value)),
            None,
        )

        if not opt:
            return []

        extra = opt.extra or {}

        # Group → multiple tables
        if extra.get("is_group"):
            tables = []
            lines = metadata_cache.get_production_lines()
            for lid in extra.get("line_ids", []):
                line = lines.get(lid)
                if line:
                    tables.append(f"detection_line_{line['line_name'].lower()}")
            return tables

        # Single line → one table
        line_name = extra.get("line_name")
        if line_name:
            return [f"detection_line_{line_name.lower()}"]

        return []

    # ── SQL clause ───────────────────────────────────────────────

    def to_sql_clause(self, value: Any) -> Optional[Tuple[str, Dict]]:
        """
        The line filter does NOT contribute a SQL WHERE clause.

        Detection tables are one-per-line (detection_line_{line_code}),
        so there's no 'line_id' column to filter on.
        Instead, line selection determines WHICH TABLES to query.
        That resolution happens in QueryBuilder.resolve_table_names().

        Returns:
            Always None — line filtering is done via table name, not WHERE.
        """
        return None
