"""
FilterEngine — Auto-discovery and dynamic instantiation.

Auto-discovery pattern (no registry needed)::

    filter_name (DB) → CamelCase→snake_case → importlib → Filter class
    Filter class carries its own metadata as class attributes.

Usage::

    from new_app.services.filters.engine import filter_engine

    all_filters = filter_engine.get_all()          # list[BaseFilter]
    resolved    = filter_engine.resolve_all()       # list[dict]  (JSON-ready)
    one         = filter_engine.get_by_name("DateRangeFilter")
    validated   = filter_engine.validate_input(user_params)
"""

from __future__ import annotations

import importlib
import logging
import re
from typing import Any, Dict, List, Optional, Type

from new_app.core.cache import metadata_cache
from new_app.services.filters.base import BaseFilter, FilterConfig

logger = logging.getLogger(__name__)

# Module path where named filter classes live
_FILTER_MODULE = "new_app.services.filters.types"


def _camel_to_snake(name: str) -> str:
    """
    Convert CamelCase class name to snake_case module file name.

    ``DateRangeFilter``      → ``date_range_filter``
    ``ProductionLineFilter`` → ``production_line_filter``
    ``CurveTypeFilter``      → ``curve_type_filter``
    """
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    s = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s)
    return s.lower()


def _resolve_filter_class(class_name: str) -> Optional[Type[BaseFilter]]:
    """
    Dynamically import and return a filter class by its CamelCase name.

    ``DateRangeFilter`` → ``new_app.services.filters.types.date_range_filter``
    """
    module_name = _camel_to_snake(class_name)
    full_path = f"{_FILTER_MODULE}.{module_name}"
    try:
        module = importlib.import_module(full_path)
        cls = getattr(module, class_name, None)
        if cls and issubclass(cls, BaseFilter):
            return cls
        logger.error(
            f"[FilterEngine] {full_path} does not export '{class_name}' "
            f"as a BaseFilter subclass"
        )
    except ImportError as exc:
        logger.error(f"[FilterEngine] Cannot import {full_path}: {exc}")
    return None


class FilterEngine:
    """
    Central filter orchestrator.

    Builds filter instances on-the-fly from cached DB rows +
    class attributes.  Zero coupling — adding a new filter only
    requires a DB row and a class file in services/filters/types/.
    """

    def __init__(self) -> None:
        self._class_cache: Dict[str, Type[BaseFilter]] = {}

    # ── Build instances ──────────────────────────────────────

    def get_all(
        self,
        parent_values: Optional[Dict[str, Any]] = None,
        filter_ids: Optional[List[int]] = None,
    ) -> List[BaseFilter]:
        """
        Instantiate active filters from cache + class attributes.

        Args:
            parent_values: Parent filter values for cascade resolution.
            filter_ids: Optional whitelist of ``filter_id`` values
                (from ``layout_config.filters``).  When provided, only
                filters whose ID is in this list are returned.  When
                ``None``, **all** active filters are returned.

        Returns a list sorted by ``display_order``.
        """
        cached_filters = metadata_cache.get_filters()  # dict[int, dict]
        instances: List[BaseFilter] = []

        for _fid, row in sorted(
            cached_filters.items(), key=lambda kv: kv[1].get("display_order", 99)
        ):
            # ── Whitelist check ──────────────────────────────
            if filter_ids is not None and row["filter_id"] not in filter_ids:
                continue

            class_name = row["filter_name"]  # e.g. "DateRangeFilter"

            # ── Auto-discovery: resolve the class ────────────
            cls = self._get_class(class_name)
            if cls is None:
                logger.warning(
                    f"[FilterEngine] No class found for '{class_name}' — skipped. "
                    f"Expected file: {_camel_to_snake(class_name)}.py"
                )
                continue

            # ── Build FilterConfig from class attrs + DB row ──
            config = FilterConfig(
                filter_id=row["filter_id"],
                class_name=class_name,
                filter_type=cls.filter_type,
                param_name=cls.param_name,
                display_order=row.get("display_order", 0),
                description=row.get("description", ""),
                placeholder=cls.placeholder,
                default_value=cls.default_value,
                required=cls.required,
                options_source=cls.options_source,
                depends_on=cls.depends_on,
                ui_config=dict(cls.ui_config),  # copy, not shared ref
            )

            instances.append(cls(config))

        return instances

    # ── Resolve to JSON ──────────────────────────────────────

    def resolve_all(
        self,
        parent_values: Optional[Dict[str, Any]] = None,
        filter_ids: Optional[List[int]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return JSON-serializable list of filters with their
        resolved options (ready for frontend rendering).
        """
        return [f.to_dict(parent_values) for f in self.get_all(parent_values, filter_ids)]

    def resolve_one(
        self,
        class_name: str,
        parent_values: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Resolve a single filter by class name."""
        flt = self.get_by_name(class_name)
        if flt is None:
            return None
        return flt.to_dict(parent_values)

    # ── Look-ups ─────────────────────────────────────────────

    def get_by_name(self, class_name: str) -> Optional[BaseFilter]:
        """Find one filter by its class_name."""
        for f in self.get_all():
            if f.config.class_name == class_name:
                return f
        return None

    def get_by_param(self, param_name: str) -> Optional[BaseFilter]:
        """Find one filter by its HTTP parameter name."""
        for f in self.get_all():
            if f.config.param_name == param_name:
                return f
        return None

    # ── Validation ───────────────────────────────────────────

    def validate_input(
        self,
        user_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Validate user-supplied filter values against their filters.

        Returns::

            {
                "valid": True/False,
                "errors": {"param_name": "message", ...},
                "cleaned": {"param_name": cleaned_value, ...},
            }
        """
        errors: Dict[str, str] = {}
        cleaned: Dict[str, Any] = {}

        for flt in self.get_all():
            pname = flt.config.param_name
            raw = user_params.get(pname)

            # Use default if nothing provided
            if raw is None:
                raw = flt.get_default()

            if not flt.validate(raw):
                errors[pname] = f"Valor inválido para {flt.config.class_name}"
            else:
                cleaned[pname] = raw

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "cleaned": cleaned,
        }

    # ── Private ──────────────────────────────────────────────

    def _get_class(self, class_name: str) -> Optional[Type[BaseFilter]]:
        """Resolve and cache a filter class by CamelCase name."""
        if class_name in self._class_cache:
            return self._class_cache[class_name]
        cls = _resolve_filter_class(class_name)
        if cls:
            self._class_cache[class_name] = cls
        return cls


# ── Singleton ────────────────────────────────────────────────
filter_engine = FilterEngine()
