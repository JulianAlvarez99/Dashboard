"""
WidgetEngine — Auto-discovery of widgets from the global DB.

How it works:
1. Reads widget_catalog from MetadataCache (loaded from camet_global DB).
2. For each widget row, tries to import the corresponding Python class.
3. If the class exists → creates an instance.
   If not → creates a "placeholder" BaseWidget with just the config.
4. All widgets are available for serialization to the frontend.

Phase 3: Discovery only, no data processing.
"""

import importlib
import logging
from typing import Dict, List, Optional

from dashboard_saas.core.cache import metadata_cache
from dashboard_saas.services.filters.base import camel_to_snake
from dashboard_saas.services.widgets.base import BaseWidget, WidgetConfig

logger = logging.getLogger(__name__)


class WidgetEngine:
    """
    Discovers and manages widget instances.

    Usage:
        engine = WidgetEngine()
        engine.load_widgets()                  # auto-discover from cache
        widgets = engine.get_all()             # list of BaseWidget instances
        widget = engine.get("KpiTotalProduction")  # by widget_name
    """

    def __init__(self):
        # widget_name → BaseWidget instance
        self._widgets: Dict[str, BaseWidget] = {}

    def load_widgets(self) -> None:
        """
        Auto-discover widgets from the MetadataCache.

        For each widget in widget_catalog, tries to import the class.
        If not found, stores a placeholder BaseWidget instance.
        """
        self._widgets.clear()

        catalog = metadata_cache.get_widget_catalog()
        if not catalog:
            logger.warning("No widgets found in cache — is cache loaded?")
            return

        for widget_id, row in catalog.items():
            widget_name = row["widget_name"]  # CamelCase

            config = WidgetConfig(
                widget_id=widget_id,
                widget_name=widget_name,
                description=row.get("description", ""),
            )

            # Try to import the specific widget class
            widget_class = self._import_widget_class(widget_name)

            if widget_class:
                instance = widget_class(config)
            else:
                # Placeholder — widget discovered but no Python class yet
                instance = BaseWidget(config)

            self._widgets[widget_name] = instance
            logger.info("Loaded widget: %s (has_class=%s)", widget_name, widget_class is not None)

        logger.info("WidgetEngine loaded %d widgets", len(self._widgets))

    def _import_widget_class(self, class_name: str) -> Optional[type]:
        """
        Dynamically import a widget class by CamelCase name.

        "KpiTotalProduction" → dashboard_saas.services.widgets.types.kpi_total_production
        """
        module_name = camel_to_snake(class_name)
        full_module = f"dashboard_saas.services.widgets.types.{module_name}"

        try:
            module = importlib.import_module(full_module)
            cls = getattr(module, class_name)
            if not issubclass(cls, BaseWidget):
                logger.warning("%s is not a BaseWidget subclass — using placeholder", class_name)
                return None
            return cls
        except ModuleNotFoundError:
            # Expected: widget class not implemented yet (Phase 3)
            logger.debug("Widget module not found: %s — using placeholder", full_module)
            return None
        except AttributeError:
            logger.warning("Class %s not found in %s — using placeholder", class_name, full_module)
            return None

    # ── Accessors ───────────────────────────────────────────────

    def get_all(self) -> List[BaseWidget]:
        """Return all loaded widgets, sorted by order."""
        return sorted(
            self._widgets.values(),
            key=lambda w: w.order,
        )

    def get(self, widget_name: str) -> Optional[BaseWidget]:
        """Get a widget by name."""
        return self._widgets.get(widget_name)

    def get_all_serialized(self) -> List[Dict]:
        """Serialize all widgets for the frontend."""
        return [w.to_dict() for w in self.get_all()]

# ── Singleton ────────────────────────────────────────────────────
widget_engine = WidgetEngine()
