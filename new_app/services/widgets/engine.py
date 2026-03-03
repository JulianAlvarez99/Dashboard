"""
WidgetEngine — Dynamic widget instantiation via Auto-Discovery.

Single Responsibility: given a list of widget class names, instantiate
the correct concrete class and execute ``process()``.

Auto-discovery pattern (no registry needed)::

    class_name (DB) → CamelCase→snake_case → importlib → Widget class
    Widget class carries its own metadata as class attributes.

Usage::

    from new_app.services.widgets.engine import widget_engine

    results = widget_engine.process_widgets(
        widget_names=["KpiTotalProduction", "ProductionTimeChart"],
        detections_df=master_df,
        downtime_df=downtime_df,
        lines_queried=[1, 2],
        cleaned={...},
        widget_catalog={1: {...}, 2: {...}},
    )
"""

from __future__ import annotations

import importlib
import logging
from typing import Any, Dict, List, Optional, Type

import pandas as pd

from new_app.services.widgets.base import BaseWidget, WidgetContext, WidgetResult
from new_app.utils.naming import camel_to_snake

logger = logging.getLogger(__name__)

# Module path where concrete widgets live
_WIDGET_MODULE = "new_app.services.widgets.types"


class WidgetEngine:
    """
    Dynamic widget resolver and executor.

    Pipeline per widget:
      1. Resolve class by CamelCase→snake_case→importlib (no registry lookup).
      2. Read metadata from class attributes (required_columns, default_config).
      3. Build WidgetContext with pre-scoped data.
      4. Call ``widget.process()`` → WidgetResult.
    """

    def __init__(self) -> None:
        # Cache: class_name → class object (avoids repeated imports)
        self._class_cache: Dict[str, Type[BaseWidget]] = {}
        # Reverse map: class_name → widget_id (built lazily, reset on cache reload)
        self._class_to_id: Dict[str, int] = {}

    def _ensure_reverse_map(self, widget_catalog: Dict[int, Dict[str, Any]]) -> None:
        """Build class_name → widget_id reverse map once per catalog load."""
        if self._class_to_id:
            return  # already built
        for wid, info in widget_catalog.items():
            name = info.get("widget_name", "")
            if name:
                self._class_to_id[name] = wid

    def process_widgets(
        self,
        widget_names: List[str],
        detections_df: pd.DataFrame,
        downtime_df: pd.DataFrame,
        lines_queried: List[int],
        cleaned: Dict[str, Any],
        widget_catalog: Dict[int, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Process a batch of widgets and return their results.

        Args:
            widget_names:   Class names from WIDGET_REGISTRY.
            detections_df:  Enriched master DataFrame.
            downtime_df:    Unified downtime DataFrame.
            lines_queried:  Line IDs that were queried.
            cleaned:        Validated filter params.
            widget_catalog: Cache data: {widget_id: {widget_name, description}}.

        Returns:
            List of serialized WidgetResult dicts.
        """
        results: List[Dict[str, Any]] = []

        for class_name in widget_names:
            result = self._process_single(
                class_name=class_name,
                detections_df=detections_df,
                downtime_df=downtime_df,
                lines_queried=lines_queried,
                cleaned=cleaned,
                widget_catalog=widget_catalog,
            )
            results.append(result)

        return results

    def _process_single(
        self,
        class_name: str,
        detections_df: pd.DataFrame,
        downtime_df: pd.DataFrame,
        lines_queried: List[int],
        cleaned: Dict[str, Any],
        widget_catalog: Dict[int, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Process one widget and return its serialized result."""
        # 1. Resolve concrete class (auto-discovery — no registry needed)
        widget_cls = self._resolve_class(class_name)
        if widget_cls is None:
            return self._error_result(
                class_name, f"Class '{class_name}' not found in {_WIDGET_MODULE}",
            )

        # 2. Resolve widget_id and display_name from catalog
        widget_id, display_name = self._resolve_catalog_info(
            class_name, widget_catalog,
        )

        # 3. Build context — read metadata from class attributes
        ctx = WidgetContext(
            widget_id=widget_id,
            widget_name=class_name,
            display_name=display_name,
            data=self._scope_data(widget_cls, detections_df),
            downtime=downtime_df,
            lines_queried=lines_queried,
            params=cleaned,
            config=dict(widget_cls.default_config),  # copy, not shared ref
        )

        # 4. Execute
        try:
            widget = widget_cls(ctx)
            result = widget.process()
            return result.to_dict()
        except Exception as exc:
            logger.error(
                f"[WidgetEngine] Error processing '{class_name}': {exc}",
                exc_info=True,
            )
            return self._error_result(class_name, str(exc))

    def _resolve_class(self, class_name: str) -> Optional[Type[BaseWidget]]:
        """
        Import and cache the widget class by its name.

        Converts CamelCase class name to snake_case module name:
          ``KpiTotalProduction`` → ``kpi_total_production``
        """
        if class_name in self._class_cache:
            return self._class_cache[class_name]

        module_name = self._class_to_module(class_name)
        full_path = f"{_WIDGET_MODULE}.{module_name}"

        try:
            module = importlib.import_module(full_path)
            cls = getattr(module, class_name, None)
            if cls and issubclass(cls, BaseWidget):
                self._class_cache[class_name] = cls
                return cls
            logger.error(
                f"[WidgetEngine] {full_path} does not export '{class_name}' "
                f"as a BaseWidget subclass"
            )
        except ImportError as exc:
            logger.error(f"[WidgetEngine] Cannot import {full_path}: {exc}")

        return None

    @staticmethod
    def _class_to_module(class_name: str) -> str:
        """
        Convert CamelCase to snake_case for module resolution.

        Delegates to the canonical ``camel_to_snake`` utility (DRY).
        ``KpiTotalProduction``  → ``kpi_total_production``
        """
        return camel_to_snake(class_name)

    @staticmethod
    def _scope_data(
        widget_cls: type,
        master_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Apply Data Scoping — return only required_columns.

        Reads ``cls.required_columns`` class attribute directly.
        If empty, the widget receives the full DataFrame.
        """
        if master_df.empty:
            return master_df

        required = widget_cls.required_columns
        if not required:
            return master_df

        available = [c for c in required if c in master_df.columns]
        # Always include detected_at and line_id if present (needed by most widgets)
        for essential in ("detected_at", "line_id"):
            if essential in master_df.columns and essential not in available:
                available.append(essential)

        return master_df[available] if available else master_df

    def _resolve_catalog_info(
        self,
        class_name: str,
        widget_catalog: Dict[int, Dict[str, Any]],
    ) -> tuple[int, str]:
        """Find widget_id and display_name from the cached catalog (O(1))."""
        self._ensure_reverse_map(widget_catalog)
        wid = self._class_to_id.get(class_name)
        if wid is not None:
            return wid, widget_catalog[wid].get("description", class_name)
        # Fallback: class_name as display, id=0
        return 0, class_name

    @staticmethod
    def _error_result(class_name: str, error: str) -> Dict[str, Any]:
        """Build an error result dict for a failed widget."""
        return {
            "widget_id": 0,
            "widget_name": class_name,
            "widget_type": "error",
            "data": None,
            "metadata": {"error": True, "message": error},
        }


# ── Singleton ────────────────────────────────────────────────────
widget_engine = WidgetEngine()
