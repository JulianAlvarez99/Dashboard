"""
DataBroker — Routes widgets to internal DataFrame or external API.

Single Responsibility: given a list of widgets and a master DataFrame,
produce a ``dict[widget_name, payload]`` where each widget gets ONLY
the data it needs, from the correct source.

Decision logic per widget:
  source_type == "internal" → slice the master DataFrame using
                               ``required_columns`` (Data Scoping).
  source_type == "external" → call ExternalAPIService with the
                               widget's ``api_source_id``.

This is the "Orquestador de Fuentes" described in Etapa 4 of
Planificacion_refactor.md.

Usage::

    from new_app.services.broker.data_broker import data_broker

    payloads = await data_broker.resolve(widget_names, master_df)
    # payloads["KpiTotalProduction"] == {"source": "internal", "data": <sliced df>}
    # payloads["ExternalWidget"]     == {"source": "external", "data": {...}}
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from new_app.services.broker.external_api_service import external_api_service
from new_app.services.widgets.engine import widget_engine

logger = logging.getLogger(__name__)

# Result type for a single widget
WidgetPayload = Dict[str, Any]


class DataBroker:
    """
    Orquestador de Fuentes — routes data for each widget.

    Used by the Orchestration Pipeline (Etapa 6) to supply
    each widget its specific data fragment.
    """

    async def resolve(
        self,
        widget_names: List[str],
        master_df: Optional[pd.DataFrame] = None,
    ) -> Dict[str, WidgetPayload]:
        """
        resolve data for a batch of widgets.

        Args:
            widget_names: list of widget class names.
            master_df:    the enriched master DataFrame from Etapa 3.
                          Required for internal widgets; may be None if all
                          widgets are external.

        Returns:
            Dict mapping widget_name → WidgetPayload:
              ``{"source": "internal"|"external", "data": ..., "ok": bool, "error": str|None}``
        """
        internal, external = self._classify(widget_names)

        # Fire external requests concurrently
        external_task = self._resolve_external(external) if external else {}

        # Internal slicing is synchronous (CPU-bound, fast)
        internal_results = self._resolve_internal(internal, master_df)

        # Await external results if any
        if asyncio.isfuture(external_task) or asyncio.iscoroutine(external_task):
            external_results = await external_task
        else:
            external_results = external_task

        return {**internal_results, **external_results}

    def resolve_internal_single(
        self,
        widget_name: str,
        master_df: pd.DataFrame,
    ) -> WidgetPayload:
        """
        Slice the DataFrame for one internal widget (synchronous).
        """
        cls = widget_engine._resolve_class(widget_name)
        if cls is None:
            return self._unknown_widget(widget_name)
        return self._slice_dataframe_cls(widget_name, cls, master_df)

    async def resolve_external_single(
        self,
        widget_name: str,
    ) -> WidgetPayload:
        """Fetch data for one external widget."""
        cls = widget_engine._resolve_class(widget_name)
        if cls is None:
            return self._unknown_widget(widget_name)

        # For external widgets, the api_source_id lives in the DB catalog,
        # not in the class. Raise a clear error if not configured.
        return {
            "source": "external",
            "ok": False,
            "error": f"Widget '{widget_name}' external data not yet configured",
            "data": None,
        }

    # ─────────────────────────────────────────────────────────
    #  INTERNAL HELPERS
    # ─────────────────────────────────────────────────────────

    @staticmethod
    def _classify(
        widget_names: List[str],
    ) -> tuple[List[str], List[str]]:
        """
        Split widgets into internal and external lists.
        All current widgets are internal (source_type determined by class).
        Unresolvable widgets are treated as internal so they surface an error.
        """
        internal: List[str] = []
        external: List[str] = []

        for name in widget_names:
            # All widgets are internal unless explicitly external
            # (external support is future work)
            internal.append(name)

        return internal, external

    def _resolve_internal(
        self,
        widget_names: List[str],
        master_df: Optional[pd.DataFrame],
    ) -> Dict[str, WidgetPayload]:
        """Slice the master DataFrame for each internal widget."""
        results: Dict[str, WidgetPayload] = {}

        for name in widget_names:
            cls = widget_engine._resolve_class(name)
            if cls is None:
                results[name] = self._unknown_widget(name)
                continue

            if master_df is None or master_df.empty:
                results[name] = {
                    "source": "internal",
                    "ok": True,
                    "error": None,
                    "data": pd.DataFrame(),
                }
                continue

            results[name] = self._slice_dataframe_cls(name, cls, master_df)

        return results

    async def _resolve_external(
        self,
        widget_names: List[str],
    ) -> Dict[str, WidgetPayload]:
        """Fetch data for all external widgets concurrently."""
        # Note: external support is future work
        # For now return error for any external widget
        results: Dict[str, WidgetPayload] = {}
        for name in widget_names:
            results[name] = {
                "source": "external",
                "ok": False,
                "error": f"Widget '{name}' external data not yet configured",
                "data": None,
            }
        return results

    @staticmethod
    def _slice_dataframe_cls(
        widget_name: str,
        widget_cls: type,
        master_df: pd.DataFrame,
    ) -> WidgetPayload:
        """
        Apply Data Scoping using class attributes.
        Reads ``cls.required_columns`` directly — no registry needed.
        """
        required = widget_cls.required_columns

        if not required:
            sliced = master_df
        else:
            available = [c for c in required if c in master_df.columns]
            missing = set(required) - set(available)
            if missing:
                logger.warning(
                    f"[DataBroker] Widget '{widget_name}' wants columns "
                    f"{missing} but they are not in the DataFrame"
                )
            sliced = master_df[available] if available else master_df

        return {
            "source": "internal",
            "ok": True,
            "error": None,
            "data": sliced,
        }

    @staticmethod
    def _unknown_widget(widget_name: str) -> WidgetPayload:
        """Return error payload for unknown widget class."""
        logger.warning(
            f"[DataBroker] No class found for widget '{widget_name}' — check file name"
        )
        return {
            "source": "unknown",
            "ok": False,
            "error": f"Widget '{widget_name}' not registered",
            "data": None,
        }


# ── Singleton ────────────────────────────────────────────────────
data_broker = DataBroker()
