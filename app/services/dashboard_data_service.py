"""
DashboardDataService — Orchestrator for the single-query data pipeline.

Responsibilities (SRP):
  1. Determine which production lines to query.
  2. Fetch & enrich raw data (detections + downtime) via DataAggregator.
  3. Dispatch each widget to the appropriate processor function.
  4. Return a unified response dict.

All widget-specific logic lives in ``app.services.processors``.
"""

from typing import Dict, List, Any
from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import metadata_cache
from app.services.widgets.base import FilterParams
from app.services.widgets.aggregators import DataAggregator
from app.services.processors import (
    PROCESSOR_MAP,
    CHART_TYPES,
    infer_widget_type,
)


# ─────────────────────────────────────────────────────────────────────
# Data container
# ─────────────────────────────────────────────────────────────────────

class DashboardData:
    """Holds enriched DataFrames ready for widget processing."""

    def __init__(
        self,
        detections: pd.DataFrame,
        downtime: pd.DataFrame,
        params: FilterParams,
        lines_queried: List[int],
    ):
        self.detections = detections
        self.downtime = downtime
        self.params = params
        self.lines_queried = lines_queried

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


# ─────────────────────────────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────────────────────────────

class DashboardDataService:
    """
    Orchestrator for the single-query dashboard data pipeline.

    Usage::

        service = DashboardDataService(session)
        result = await service.get_dashboard_data(params, widget_ids)
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.aggregator = DataAggregator(session)

    # ── Public entry point ───────────────────────────────────────────

    async def get_dashboard_data(
        self,
        params: FilterParams,
        widget_ids: List[int],
    ) -> Dict[str, Any]:
        """Fetch all data, process every requested widget, return unified response."""
        line_ids = self.aggregator.get_line_ids_from_params(params)
        dashboard_data = await self._fetch_all_data(line_ids, params)

        widgets_result: Dict[str, Any] = {}
        for widget_id in widget_ids:
            widgets_result[str(widget_id)] = self._process_widget(
                widget_id, dashboard_data
            )

        return {
            "widgets": widgets_result,
            "metadata": {
                "total_detections": dashboard_data.total_detections,
                "total_downtime_events": dashboard_data.total_downtime_events,
                "lines_queried": line_ids,
                "period": {
                    "start": str(params.start_date or params.start_datetime or ""),
                    "end": str(params.end_date or params.end_datetime or ""),
                },
                "interval": params.interval,
                "timestamp": datetime.now().isoformat(),
            },
        }

    # ── Data fetching ────────────────────────────────────────────────

    async def _fetch_all_data(
        self, line_ids: List[int], params: FilterParams
    ) -> DashboardData:
        """Fetch detections + downtime for all lines, then enrich with metadata."""
        # --- Detections ---
        raw_detections = await self.aggregator.fetch_detections_multi_line(
            line_ids, params
        )
        enriched_detections = pd.DataFrame()
        if not raw_detections.empty:
            enriched_detections = self.aggregator.enrich_with_metadata(raw_detections)
            if "line_id" in enriched_detections.columns:
                enriched_detections = self.aggregator.enrich_with_line_metadata(
                    enriched_detections
                )

        # --- Downtime ---
        raw_downtime = await self._fetch_downtime_events(line_ids, params)
        enriched_downtime = pd.DataFrame()
        if not raw_downtime.empty:
            enriched_downtime = self._enrich_downtime(raw_downtime)

        return DashboardData(
            detections=enriched_detections,
            downtime=enriched_downtime,
            params=params,
            lines_queried=line_ids,
        )

    async def _fetch_downtime_events(
        self, line_ids: List[int], params: FilterParams
    ) -> pd.DataFrame:
        """Fetch downtime events for multiple production lines."""
        dataframes: List[pd.DataFrame] = []

        for line_id in line_ids:
            line = metadata_cache.get_production_line(line_id)
            if not line:
                continue
            table_name = f"downtime_events_{line['line_name'].lower()}"
            query, bind_params = self._build_downtime_query(table_name, params)
            try:
                result = await self.session.execute(text(query), bind_params)
                rows = result.mappings().all()
                if rows:
                    df = pd.DataFrame([dict(r) for r in rows])
                    df["line_id"] = line_id
                    dataframes.append(df)
            except Exception:
                continue  # table might not exist

        return pd.concat(dataframes, ignore_index=True) if dataframes else pd.DataFrame()

    # ── Downtime SQL builder ─────────────────────────────────────────

    @staticmethod
    def _build_downtime_query(table_name: str, params: FilterParams) -> tuple:
        query = f"""
            SELECT event_id, last_detection_id, start_time, end_time,
                   duration, reason_code, reason, is_manual, created_at
            FROM {table_name}
            WHERE 1=1
        """
        bp: Dict[str, Any] = {}
        effective_start, effective_end = params.get_effective_datetimes()

        if effective_start:
            query += " AND start_time >= :start_dt"
            bp["start_dt"] = effective_start
        elif params.start_date:
            query += " AND DATE(start_time) >= :start_date"
            bp["start_date"] = params.start_date

        if effective_end:
            query += " AND end_time <= :end_dt"
            bp["end_dt"] = effective_end
        elif params.end_date:
            query += " AND DATE(end_time) <= :end_date"
            bp["end_date"] = params.end_date

        # Shift time-of-day filter
        if params.shift_id:
            from app.core.cache import metadata_cache as _mc
            shift = _mc.get_shifts().get(params.shift_id)
            if shift:
                from datetime import timedelta
                s_time = shift.get("start_time")
                e_time = shift.get("end_time")
                is_overnight = shift.get("is_overnight", False)

                def _t2s(v):
                    if isinstance(v, timedelta):
                        total = int(v.total_seconds())
                        h, rem = divmod(total, 3600)
                        m, s = divmod(rem, 60)
                        return f"{h:02d}:{m:02d}:{s:02d}"
                    if hasattr(v, "hour"):
                        return f"{v.hour:02d}:{v.minute:02d}:{v.second:02d}"
                    return None

                s_str = _t2s(s_time)
                e_str = _t2s(e_time)
                if s_str and e_str:
                    if is_overnight or e_str <= s_str:
                        query += " AND (TIME(start_time) >= :shift_start OR TIME(start_time) < :shift_end)"
                    else:
                        query += " AND TIME(start_time) >= :shift_start AND TIME(start_time) < :shift_end"
                    bp["shift_start"] = s_str
                    bp["shift_end"] = e_str

        query += " ORDER BY start_time"
        return query, bp

    # ── Enrichment ───────────────────────────────────────────────────

    @staticmethod
    def _enrich_downtime(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or "line_id" not in df.columns:
            return df
        lines = metadata_cache.get_production_lines()
        df["line_name"] = df["line_id"].map(
            lambda x: lines.get(x, {}).get("line_name", "Desconocida")
        )
        df["line_code"] = df["line_id"].map(
            lambda x: lines.get(x, {}).get("line_code", "")
        )
        if "start_time" in df.columns:
            df["start_time"] = pd.to_datetime(df["start_time"])
        if "end_time" in df.columns:
            df["end_time"] = pd.to_datetime(df["end_time"])
        return df

    # ── Widget dispatch ──────────────────────────────────────────────

    def _process_widget(
        self, widget_id: int, data: DashboardData
    ) -> Dict[str, Any]:
        """Resolve widget type, pick the right processor, call it."""
        widget_meta = metadata_cache.get_widget(widget_id)
        if not widget_meta:
            return {
                "widget_id": widget_id,
                "widget_type": "unknown",
                "data": None,
                "metadata": {"error": f"Widget {widget_id} not found in catalog"},
            }

        widget_name = widget_meta["widget_name"]
        widget_type = infer_widget_type(widget_name)

        processor = PROCESSOR_MAP.get(widget_type)
        if not processor:
            return {
                "widget_id": widget_id,
                "widget_name": widget_name,
                "widget_type": widget_type,
                "data": None,
                "metadata": {"message": "Widget type not implemented"},
            }

        # Chart processors need the aggregator; KPI/table processors do not.
        if widget_type in CHART_TYPES:
            return processor(widget_id, widget_name, widget_type, data, self.aggregator)
        return processor(widget_id, widget_name, widget_type, data)
