"""
FilterEngine — Auto-discovery and instantiation of filters.

How it works:
1. Reads active filters from MetadataCache (loaded from DB).
2. For each filter row, derives the Python module name from the CamelCase
   class name: "ProductionLineFilter" → "production_line_filter".
3. Dynamically imports the class from services/filters/types/{module_name}.py.
4. Creates an instance with a FilterConfig that merges DB data + class attrs.
5. Stores all instances for use by the dashboard route and API.
"""

import importlib
import logging
from typing import Dict, List, Optional

from dashboard_saas.core.cache import metadata_cache
from dashboard_saas.services.filters.base import BaseFilter, FilterConfig, camel_to_snake

logger = logging.getLogger(__name__)


class FilterEngine:
    """
    Discovers and manages filter instances.

    Usage:
        engine = FilterEngine()
        engine.load_filters()               # auto-discover from cache
        filters = engine.get_all()           # list of BaseFilter instances
        line_filter = engine.get("line_id")  # by param_name
    """

    def __init__(self):
        # param_name → BaseFilter instance
        self._filters: Dict[str, BaseFilter] = {}

    def load_filters(self) -> None:
        """
        Auto-discover filters from the MetadataCache.

        For each active filter in the DB, imports the corresponding
        Python class and creates an instance.
        """
        self._filters.clear()

        # Get active filters from cache (loaded in Phase 2)
        cached_filters = metadata_cache.get_filters()
        if not cached_filters:
            logger.warning("No filters found in cache — is cache loaded?")
            return

        for filter_id, row in cached_filters.items():
            filter_name = row["filter_name"]  # CamelCase, e.g. "ProductionLineFilter"

            try:
                # Import the filter class dynamically
                filter_class = self._import_filter_class(filter_name)
                if filter_class is None:
                    continue

                # Build the config from DB row + class attributes
                config = FilterConfig(
                    filter_id=filter_id,
                    filter_name=filter_name,
                    description=row.get("description", ""),
                    display_order=row.get("display_order", 0),
                    additional_filter=row.get("additional_filter"),
                    filter_type=getattr(filter_class, "filter_type", ""),
                    param_name=getattr(filter_class, "param_name", ""),
                    required=getattr(filter_class, "required", False),
                    placeholder=getattr(filter_class, "placeholder", ""),
                    default_value=getattr(filter_class, "default_value", None),
                    ui_config=getattr(filter_class, "ui_config", {}),
                )

                # Create instance
                instance = filter_class(config)
                self._filters[instance.param_name] = instance

                logger.info(
                    "Loaded filter: %s (param=%s, type=%s)",
                    filter_name, instance.param_name, instance.filter_type,
                )

            except Exception as e:
                logger.error("Failed to load filter %s: %s", filter_name, e, exc_info=True)

        logger.info("FilterEngine loaded %d filters", len(self._filters))

    def _import_filter_class(self, class_name: str) -> Optional[type]:
        """
        Dynamically import a filter class by its CamelCase name.

        "ProductionLineFilter" → imports from
        dashboard_saas.services.filters.types.production_line_filter
        and returns the class ProductionLineFilter.
        """
        module_name = camel_to_snake(class_name)
        full_module = f"dashboard_saas.services.filters.types.{module_name}"

        try:
            module = importlib.import_module(full_module)
            cls = getattr(module, class_name)
            if not issubclass(cls, BaseFilter):
                logger.warning("%s is not a BaseFilter subclass — skipping", class_name)
                return None
            return cls
        except ModuleNotFoundError:
            logger.warning(
                "Filter module not found: %s (expected at %s) — skipping",
                class_name, full_module
            )
            return None
        except AttributeError:
            logger.warning(
                "Class %s not found in module %s — skipping",
                class_name, full_module
            )
            return None

    # ── Accessors ───────────────────────────────────────────────

    def get_all(self) -> List[BaseFilter]:
        """Return all loaded filter instances, sorted by display_order."""
        return sorted(
            self._filters.values(),
            key=lambda f: f.config.display_order,
        )

    def get(self, param_name: str) -> Optional[BaseFilter]:
        """Get a filter by its param_name."""
        return self._filters.get(param_name)

    def get_all_serialized(self) -> List[Dict]:
        """Serialize all filters for the frontend (template rendering)."""
        return [f.to_dict() for f in self.get_all()]

    def validate_request(self, filter_values: Dict) -> List[str]:
        """
        Validate incoming payload against all active filters.
        Checks for missing required fields or invalid options.
        Returns a list of error messages (empty if valid).
        """
        errors = []
        for flt in self.get_all():
            val = filter_values.get(flt.param_name)
            if not flt.validate(val):
                name = flt.config.description or flt.param_name
                errors.append(f"Falta un valor válido para: {name}")
        return errors

    def get_target_tables(self, filter_values: Dict) -> List[str]:
        """
        Ask all filters for target tables and merge the results.
        If a partition filter (like lines) exists, it will supply the tables.
        """
        tables = set()
        for param_name, value in filter_values.items():
            flt = self._filters.get(param_name)
            if flt:
                for t in flt.get_target_tables(value):
                    tables.add(t)
        return list(tables)

    def collect_sql_clauses(self, filter_values: Dict) -> tuple:
        """
        Collect SQL clauses from all filters based on user input.

        Args:
            filter_values: { param_name: value, ... } from the frontend.

        Returns:
            (list_of_clauses, merged_params) ready for QueryBuilder.
        """
        clauses = []
        params = {}

        for param_name, value in filter_values.items():
            flt = self._filters.get(param_name)
            if flt is None:
                # We do not crash if frontend sends extra keys, we just ignore them
                continue

            result = flt.to_sql_clause(value)
            if result is not None:
                clause, clause_params = result
                clauses.append(clause)
                params.update(clause_params)

        return clauses, params

# ── Singleton ────────────────────────────────────────────────────
filter_engine = FilterEngine()
