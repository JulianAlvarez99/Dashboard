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

from new_app.config.widget_registry import WIDGET_REGISTRY
from new_app.services.broker.external_api_service import external_api_service

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
        Resolve data for a batch of widgets.

        Args:
            widget_names: list of widget class names (keys in WIDGET_REGISTRY).
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

        Useful when widgets are processed one at a time.
        """
        config = WIDGET_REGISTRY.get(widget_name)
        if config is None:
            return self._unknown_widget(widget_name)

        return self._slice_dataframe(widget_name, config, master_df)

    async def resolve_external_single(
        self,
        widget_name: str,
    ) -> WidgetPayload:
        """
        Fetch data for one external widget.
        """
        config = WIDGET_REGISTRY.get(widget_name)
        if config is None:
            return self._unknown_widget(widget_name)

        api_source_id = config.get("api_source_id")
        if not api_source_id:
            return {
                "source": "external",
                "ok": False,
                "error": f"Widget '{widget_name}' has no api_source_id configured",
                "data": None,
            }

        result = await external_api_service.fetch(api_source_id)
        return {
            "source": "external",
            "ok": result["ok"],
            "error": result.get("error"),
            "data": result.get("data"),
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

        Unregistered widgets are silently included as "internal"
        so they surface an error in _resolve_internal.
        """
        internal: List[str] = []
        external: List[str] = []

        for name in widget_names:
            config = WIDGET_REGISTRY.get(name)
            if config and config.get("source_type") == "external":
                external.append(name)
            else:
                internal.append(name)

        return internal, external

    def _resolve_internal(
        self,
        widget_names: List[str],
        master_df: Optional[pd.DataFrame],
    ) -> Dict[str, WidgetPayload]:
        """
        Slice the master DataFrame for each internal widget.
        """
        results: Dict[str, WidgetPayload] = {}

        for name in widget_names:
            config = WIDGET_REGISTRY.get(name)
            if config is None:
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

            results[name] = self._slice_dataframe(name, config, master_df)

        return results

    async def _resolve_external(
        self,
        widget_names: List[str],
    ) -> Dict[str, WidgetPayload]:
        """
        Fetch data for all external widgets concurrently.
        """
        # Collect api_source_ids
        api_map: Dict[str, str] = {}  # widget_name → api_source_id
        results: Dict[str, WidgetPayload] = {}

        for name in widget_names:
            config = WIDGET_REGISTRY.get(name, {})
            api_id = config.get("api_source_id")
            if api_id:
                api_map[name] = api_id
            else:
                results[name] = {
                    "source": "external",
                    "ok": False,
                    "error": f"Widget '{name}' has no api_source_id",
                    "data": None,
                }

        if not api_map:
            return results

        # Deduplicate: multiple widgets might share the same API
        unique_api_ids = list(set(api_map.values()))
        api_results = await external_api_service.fetch_many(unique_api_ids)

        # Map results back to widgets
        for widget_name, api_id in api_map.items():
            raw = api_results.get(api_id, {})
            results[widget_name] = {
                "source": "external",
                "ok": raw.get("ok", False),
                "error": raw.get("error"),
                "data": raw.get("data"),
            }

        return results

    @staticmethod
    def _slice_dataframe(
        widget_name: str,
        config: dict,
        master_df: pd.DataFrame,
    ) -> WidgetPayload:
        """
        Apply Data Scoping — return only the columns required by the widget.

        If ``required_columns`` is empty, the widget receives the
        full DataFrame (e.g., DowntimeTable needs all columns).
        """
        required = config.get("required_columns", [])

        if not required:
            # Widget needs the full DataFrame
            sliced = master_df
        else:
            # Only include columns that actually exist in the DataFrame
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
        """Return error payload for unregistered widget."""
        logger.warning(
            f"[DataBroker] Widget '{widget_name}' not found in WIDGET_REGISTRY"
        )
        return {
            "source": "unknown",
            "ok": False,
            "error": f"Widget '{widget_name}' not registered",
            "data": None,
        }


# ── Singleton ────────────────────────────────────────────────────
data_broker = DataBroker()
