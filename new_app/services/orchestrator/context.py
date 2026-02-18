"""
DashboardContext — Immutable data container for a dashboard request.

Holds the enriched DataFrames, filter params, and widget metadata
produced by the pipeline.  Created once by ``DashboardOrchestrator``,
then consumed read-only by ``WidgetEngine``.

This is the "context of data" described in Etapa 6 Phase 6.2.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd


class DashboardContext:
    """
    All data + metadata needed to process widgets for one request.

    Attributes:
        detections:     Enriched master DataFrame (Etapa 3 output).
        downtime:       Unified downtime DataFrame (DB + gap-calculated).
        cleaned:        Validated filter parameters.
        line_ids:       Production line IDs that were queried.
        is_multi_line:  Whether more than one line was queried.
        widget_names:   Class names of widgets to render.
        widget_catalog: Full widget_catalog cache (id → metadata).
    """

    __slots__ = (
        "detections",
        "downtime",
        "cleaned",
        "line_ids",
        "is_multi_line",
        "widget_names",
        "widget_catalog",
    )

    def __init__(
        self,
        detections: pd.DataFrame,
        downtime: pd.DataFrame,
        cleaned: Dict[str, Any],
        line_ids: List[int],
        widget_names: List[str],
        widget_catalog: Dict[int, Dict[str, Any]],
    ):
        self.detections = detections
        self.downtime = downtime
        self.cleaned = cleaned
        self.line_ids = line_ids
        self.is_multi_line = len(line_ids) > 1
        self.widget_names = widget_names
        self.widget_catalog = widget_catalog

    # ── Read-only helpers ────────────────────────────────────

    @property
    def has_detections(self) -> bool:
        return not self.detections.empty

    @property
    def has_downtime(self) -> bool:
        return not self.downtime.empty

    @property
    def total_detections(self) -> int:
        return len(self.detections)

    @property
    def total_downtime_events(self) -> int:
        return len(self.downtime)
