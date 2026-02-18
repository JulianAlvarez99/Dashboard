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

import logging
import time
from typing import Any, Dict, List, Optional

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
      → fetch detections → fetch downtime → execute widgets → assemble
    """

    # ─────────────────────────────────────────────────────────
    #  PUBLIC API
    # ─────────────────────────────────────────────────────────

    async def execute(
        self,
        session,
        user_params: Dict[str, Any],
        tenant_id: int,
        role: str,
        widget_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        Full dashboard execution pipeline.

        Args:
            session:      Active async DB session (tenant).
            user_params:  Raw filter values from the frontend.
            tenant_id:    Current tenant ID (for layout resolution).
            role:         User role (for layout resolution).
            widget_ids:   Explicit widget IDs (bypasses layout lookup).

        Returns:
            ``{"widgets": {...}, "metadata": {...}}``
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

        # Phase 6.2 — Build data context
        ctx = await _build_context(
            session, cleaned, line_ids, widget_names, widget_catalog,
        )

        # Phase 6.4 — Execute widgets & assemble
        widgets_result = _execute_widgets(ctx)
        elapsed = time.perf_counter() - t0

        _log_summary(ctx, widgets_result, elapsed)
        return ResponseAssembler.assemble(ctx, widgets_result, elapsed)

    async def execute_quick(
        self,
        session,
        cleaned: Dict[str, Any],
        widget_names: List[str],
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
            session, cleaned, line_ids, widget_names, widget_catalog,
        )

        widgets_result = _execute_widgets(ctx)
        elapsed = time.perf_counter() - t0

        return ResponseAssembler.assemble(ctx, widgets_result, elapsed)


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
    session,
    cleaned: Dict[str, Any],
    line_ids: List[int],
    widget_names: List[str],
    widget_catalog: Dict[int, Dict[str, Any]],
) -> DashboardContext:
    """
    Phase 6.2 — Fetch enriched detections + unified downtime.

    Both data pipelines run sequentially (downtime needs detections
    for gap calculation).
    """
    detections_df = await detection_service.get_enriched_detections(
        session=session,
        line_ids=line_ids,
        cleaned=cleaned,
    )

    downtime_df = await downtime_service.get_downtime(
        session=session,
        line_ids=line_ids,
        cleaned=cleaned,
        detections_df=detections_df,
        threshold_override=cleaned.get("downtime_threshold"),
    )

    logger.info(
        f"[Orchestrator] Data context: "
        f"{len(detections_df)} detections, "
        f"{len(downtime_df)} downtime events, "
        f"{len(line_ids)} lines"
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
