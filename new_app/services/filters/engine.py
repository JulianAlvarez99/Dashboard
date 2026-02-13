"""
FilterEngine — Auto-registration and dynamic instantiation.

This is the **heart of Etapa 2**.  It:

1. Reads the ``filter`` table rows from MetadataCache.
2. Looks up each ``filter_name`` (= class name) in FILTER_REGISTRY.
3. Builds a ``FilterConfig`` merging DB metadata + registry metadata.
4. Dynamically imports the concrete filter class from
   ``new_app.services.filters.types``.
5. Instantiates it → ready to validate, provide options, build SQL.

Usage::

    from new_app.services.filters.engine import filter_engine

    # After cache is loaded (post-login):
    all_filters = filter_engine.get_all()          # list[BaseFilter]
    resolved    = filter_engine.resolve_all()       # list[dict]  (JSON-ready)
    one         = filter_engine.get_by_name("DateRangeFilter")
    validated   = filter_engine.validate_input(user_params)
"""

from __future__ import annotations

import importlib
from typing import Any, Dict, List, Optional, Type

from new_app.config.filter_registry import FILTER_REGISTRY
from new_app.core.cache import metadata_cache
from new_app.services.filters.base import BaseFilter, FilterConfig


# ── Type map: filter_type → module name holding the class ──
_TYPE_TO_MODULE: dict[str, str] = {
    "daterange":   "daterange",
    "dropdown":    "dropdown",
    "multiselect": "multiselect",
    "text":        "text",
    "number":      "number",
    "toggle":      "toggle",
}

# ── Class name per filter_type (the concrete Python class) ──
_TYPE_TO_CLASS: dict[str, str] = {
    "daterange":   "DateRangeFilter",
    "dropdown":    "DropdownFilter",
    "multiselect": "MultiselectFilter",
    "text":        "TextFilter",
    "number":      "NumberFilter",
    "toggle":      "ToggleFilter",
}


def _get_filter_class(filter_type: str) -> Optional[Type[BaseFilter]]:
    """Dynamically import and return the concrete filter class."""
    mod_name = _TYPE_TO_MODULE.get(filter_type)
    cls_name = _TYPE_TO_CLASS.get(filter_type)
    if not mod_name or not cls_name:
        return None
    module = importlib.import_module(f"new_app.services.filters.types.{mod_name}")
    return getattr(module, cls_name, None)


class FilterEngine:
    """
    Central filter orchestrator.

    Builds filter instances on-the-fly from cached DB rows +
    FILTER_REGISTRY config.  Zero coupling — adding a new filter
    only requires a DB row, a registry entry, and a class file.
    """

    # ── Build instances ──────────────────────────────────────

    def get_all(
        self,
        parent_values: Optional[Dict[str, Any]] = None,
        filter_ids: Optional[List[int]] = None,
    ) -> List[BaseFilter]:
        """
        Instantiate active filters from cache + registry.

        Args:
            parent_values: Parent filter values for cascade resolution.
            filter_ids: Optional whitelist of ``filter_id`` values
                (from ``layout_config.filters``).  When provided, only
                filters whose ID is in this list are returned.  When
                ``None``, **all** active filters are returned.

        Returns a list sorted by ``display_order``.
        """
        cached_filters = metadata_cache.get_filters()  # dict[int, dict]
        instances: list[BaseFilter] = []

        for _fid, row in sorted(
            cached_filters.items(), key=lambda kv: kv[1].get("display_order", 99)
        ):
            # ── Whitelist check ──────────────────────────────
            if filter_ids is not None and row["filter_id"] not in filter_ids:
                continue
            class_name = row["filter_name"]  # e.g. "DateRangeFilter"
            registry = FILTER_REGISTRY.get(class_name)
            if registry is None:
                print(f"[FilterEngine] WARN: '{class_name}' not in FILTER_REGISTRY — skipped")
                continue

            config = FilterConfig(
                filter_id=row["filter_id"],
                class_name=class_name,
                filter_type=registry["filter_type"],
                param_name=registry["param_name"],
                display_order=row.get("display_order", 0),
                description=row.get("description", ""),
                placeholder=registry.get("placeholder"),
                default_value=registry.get("default_value"),
                required=registry.get("required", False),
                options_source=registry.get("options_source"),
                depends_on=registry.get("depends_on"),
                ui_config=registry.get("ui_config", {}),
            )

            cls = _get_filter_class(config.filter_type)
            if cls is None:
                print(f"[FilterEngine] WARN: no class for type '{config.filter_type}'")
                continue

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

        Args:
            parent_values: For cascade resolution.
            filter_ids: Whitelist from ``layout_config.filters``.
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
        errors: dict[str, str] = {}
        cleaned: dict[str, Any] = {}

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


# ── Singleton ────────────────────────────────────────────────
filter_engine = FilterEngine()
