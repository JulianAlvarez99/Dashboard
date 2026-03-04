"""
DashboardOrchestrator — Thin coordinator for the Etapa 6 pipeline.

Single Responsibility: wire the phases together in order.
All heavy logic is delegated to specialized modules:

  Phase 6.1  → FilterEngine      (``new_app.services.filters.engine``)
  Phase 6.2  → DetectionService   (``new_app.services.data.detection_service``)
               DowntimeService    (``new_app.services.data.downtime_service``)
  Phase 6.3  → WidgetResolver     (``resolver.py``)
  Phase 6.4  → WidgetEngine       (``new_app.services.widgets.engine``)
  Assembly   → ResponseAssembler  (``assembler.py``)

Usage::

    from new_app.services.orchestrator import dashboard_orchestrator

    result = await dashboard_orchestrator.execute(
        session=session,
        user_params={...},
        tenant_id=1,
        role="ADMIN",
    )
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from new_app.core.database import db_manager
from new_app.services.data.detection_service import detection_service
from new_app.services.data.downtime_service import downtime_service
from new_app.services.data.line_resolver import line_resolver
from new_app.services.filters.engine import filter_engine
from new_app.services.widgets.engine import widget_engine

from new_app.services.orchestrator.assembler import ResponseAssembler
from new_app.services.orchestrator.context import DashboardContext
from new_app.services.orchestrator.resolver import WidgetResolver

logger = logging.getLogger(__name__)


class DashboardOrchestrator:
    """
    Master coordinator — runs the full dashboard pipeline.

    ``execute()`` flow:
      validate → resolve lines → resolve widgets
      → fetch detections + db-downtime in parallel
      → gap analysis → execute widgets → assemble
    """

    # ─────────────────────────────────────────────────────────
    #  PUBLIC API
    # ─────────────────────────────────────────────────────────

    async def execute(
        self,
        session,  # kept for API compatibility but no longer used directly
        user_params: Dict[str, Any],
        tenant_id: int,
        role: str,
        widget_ids: Optional[List[int]] = None,
        include_raw: bool = False,
        db_name: str = "",
    ) -> Dict[str, Any]:
        """
        Full dashboard execution pipeline.

        Args:
            session:      Active async DB session (kept for API compatibility;
                          pipeline now opens its own sessions internally).
            user_params:  Raw filter values from the frontend.
            tenant_id:    Current tenant ID (for layout resolution).
            role:         User role (for layout resolution).
            widget_ids:   Explicit widget IDs (bypasses layout lookup).
            include_raw:  If True, include raw detection + downtime rows
                          in the response for client-side re-aggregation.
            db_name:      Tenant database name (resolved from JWT at call site).

        Returns:
            ``{"widgets": {...}, "metadata": {...}, "raw_data": [...]}``
        """
        t0 = time.perf_counter()

        # Phase 6.1 — Validate filters
        cleaned = _validate_filters(user_params)

        # Resolve production lines
        line_ids = line_resolver.resolve(cleaned)
        if not line_ids:
            return ResponseAssembler.empty(
                "No production lines found for the given parameters",
            )

        # Phase 6.3 — Resolve which widgets to render
        widget_names, widget_catalog = await WidgetResolver.resolve(
            tenant_id, role, widget_ids,
        )
        if not widget_names:
            return ResponseAssembler.empty(
                "No widgets configured for this layout",
            )

        # Phase 6.2 — Build data context (parallel DB fetches)
        ctx = await _build_context(
            db_name=db_name,
            cleaned=cleaned,
            line_ids=line_ids,
            widget_names=widget_names,
            widget_catalog=widget_catalog,
        )

        # Phase 6.4 — Execute widgets & assemble
        widgets_result = _execute_widgets(ctx)
        elapsed = time.perf_counter() - t0

        _log_summary(ctx, widgets_result, elapsed)
        return ResponseAssembler.assemble(
            ctx,
            widgets_result,
            elapsed,
            raw_df=ctx.detections if include_raw else None,
            downtime_df=ctx.downtime if include_raw else None,
        )

    async def execute_quick(
        self,
        session,  # kept for API compatibility
        cleaned: Dict[str, Any],
        widget_names: List[str],
        include_raw: bool = False,
        db_name: str = "",
    ) -> Dict[str, Any]:
        """
        Simplified pipeline — skips validation and layout resolution.

        For internal calls, testing, or pre-validated requests.
        """
        t0 = time.perf_counter()

        line_ids = line_resolver.resolve(cleaned)
        if not line_ids:
            return ResponseAssembler.empty("No production lines resolved")

        from new_app.core.cache import metadata_cache
        widget_catalog = metadata_cache.get_widget_catalog()

        ctx = await _build_context(
            db_name=db_name,
            cleaned=cleaned,
            line_ids=line_ids,
            widget_names=widget_names,
            widget_catalog=widget_catalog,
        )

        widgets_result = _execute_widgets(ctx)
        elapsed = time.perf_counter() - t0

        return ResponseAssembler.assemble(
            ctx,
            widgets_result,
            elapsed,
            raw_df=ctx.detections if include_raw else None,
            downtime_df=ctx.downtime if include_raw else None,
        )


# ─────────────────────────────────────────────────────────────────
# Private helpers (module-level functions — no state)
# ─────────────────────────────────────────────────────────────────

def _validate_filters(user_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Phase 6.1 — Validate user-supplied filters.

    Uses best-effort: returns the cleaned values that passed
    validation even if some entries had errors.
    """
    result = filter_engine.validate_input(user_params)

    if not result["valid"]:
        logger.warning(
            f"[Orchestrator] Filter validation errors: {result['errors']}"
        )

    return result["cleaned"]


async def _build_context(
    db_name: str,
    cleaned: Dict[str, Any],
    line_ids: List[int],
    widget_names: List[str],
    widget_catalog: Dict[int, Dict[str, Any]],
) -> DashboardContext:
    """
    Phase 6.2 — Fetch enriched detections + DB downtime in parallel.

    Detections and DB-recorded downtime are fetched concurrently using
    two independent sessions (asyncio.gather), then gap analysis runs
    on the detection result.  This removes the sequential DB fetch
    bottleneck when downtime tables are large.
    """
    threshold_override = cleaned.get("downtime_threshold")

    async def _fetch_detections():
        async with db_manager.get_tenant_session_by_name(db_name) as session:
            return await detection_service.get_enriched_detections(
                session=session,
                line_ids=line_ids,
                cleaned=cleaned,
            )

    async def _fetch_db_downtime():
        async with db_manager.get_tenant_session_by_name(db_name) as session:
            return await downtime_service.get_db_downtime_only(
                session=session,
                line_ids=line_ids,
                cleaned=cleaned,
            )

    detections_df, db_downtime_df = await asyncio.gather(
        _fetch_detections(),
        _fetch_db_downtime(),
    )

    # Gap analysis requires detections — runs after the parallel fetch
    from new_app.services.data.downtime_calculator import (
        calculate_gap_downtimes,
        remove_overlapping,
    )
    calc_df = downtime_service._calculate_gap_events(
        detections_df, line_ids, threshold_override,
    )
    from new_app.services.data.downtime_service import downtime_service as ds
    if not calc_df.empty and not db_downtime_df.empty:
        from new_app.services.data.downtime_calculator import remove_overlapping
        calc_df = remove_overlapping(calc_df, db_downtime_df)

    downtime_df = ds._merge_and_enrich(db_downtime_df, calc_df)

    logger.info(
        "[Orchestrator] Data context: %d detections, %d downtime events, %d lines",
        len(detections_df), len(downtime_df), len(line_ids),
    )

    return DashboardContext(
        detections=detections_df,
        downtime=downtime_df,
        cleaned=cleaned,
        line_ids=line_ids,
        widget_names=widget_names,
        widget_catalog=widget_catalog,
    )


def _execute_widgets(ctx: DashboardContext) -> List[Dict[str, Any]]:
    """Phase 6.4 — Delegate to WidgetEngine for processing."""
    return widget_engine.process_widgets(
        widget_names=ctx.widget_names,
        detections_df=ctx.detections,
        downtime_df=ctx.downtime,
        lines_queried=ctx.line_ids,
        cleaned=ctx.cleaned,
        widget_catalog=ctx.widget_catalog,
    )


def _log_summary(
    ctx: DashboardContext,
    widgets_result: List[Dict[str, Any]],
    elapsed: float,
) -> None:
    """Log a one-line summary of the completed pipeline."""
    logger.info(
        f"[Orchestrator] Completed in {elapsed:.2f}s — "
        f"{ctx.total_detections} detections, "
        f"{ctx.total_downtime_events} downtime events, "
        f"{len(widgets_result)} widgets"
    )


# ── Singleton ────────────────────────────────────────────────────
dashboard_orchestrator = DashboardOrchestrator()
