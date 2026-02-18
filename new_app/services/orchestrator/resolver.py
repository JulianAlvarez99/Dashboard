"""
WidgetResolver — Determines which widgets a request should render.

Single Responsibility: translate (tenant_id, role, optional widget_ids)
into a concrete list of widget class names using LayoutService +
MetadataCache.

Separated from the main pipeline so layout-resolution logic can
evolve independently (e.g. user-specific overrides, A/B testing).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from new_app.core.cache import metadata_cache
from new_app.services.config.layout_service import layout_service

logger = logging.getLogger(__name__)


class WidgetResolver:
    """
    Resolves widget class names from layout configuration.

    Resolution strategy (ordered):
      1. Explicit ``widget_ids`` override → direct catalog lookup.
      2. ``dashboard_template`` for (tenant_id, role) → LayoutService.
      3. Empty list if nothing found.
    """

    @staticmethod
    async def resolve(
        tenant_id: int,
        role: str,
        widget_ids: Optional[List[int]] = None,
    ) -> tuple[List[str], Dict[int, Dict[str, Any]]]:
        """
        Resolve widget IDs to class names and return the catalog.

        Args:
            tenant_id:  Current tenant.
            role:       User role (case-insensitive match).
            widget_ids: If provided, bypasses layout lookup.

        Returns:
            ``(class_names, widget_catalog)``
        """
        catalog = metadata_cache.get_widget_catalog()

        if widget_ids:
            names = _ids_to_names(widget_ids, catalog)
            return names, catalog

        return await _resolve_from_layout(tenant_id, role, catalog)


# ── Private helpers ──────────────────────────────────────────────

def _ids_to_names(
    widget_ids: List[int],
    catalog: Dict[int, Dict[str, Any]],
) -> List[str]:
    """Map explicit widget IDs to their class names via the catalog."""
    names: List[str] = []
    for wid in widget_ids:
        info = catalog.get(wid)
        if info:
            names.append(info["widget_name"])
        else:
            logger.warning(f"[WidgetResolver] widget_id={wid} not in catalog")
    return names


async def _resolve_from_layout(
    tenant_id: int,
    role: str,
    catalog: Dict[int, Dict[str, Any]],
) -> tuple[List[str], Dict[int, Dict[str, Any]]]:
    """Load the layout template and resolve its widget IDs."""
    layout_config = await layout_service.get_layout_config(tenant_id, role)

    if layout_config is None or not layout_config.has_widgets:
        logger.warning(
            f"[WidgetResolver] No layout for tenant={tenant_id}, role={role}"
        )
        return [], catalog

    names: List[str] = []
    for wid in layout_config.enabled_widget_ids:
        info = catalog.get(wid)
        if info:
            names.append(info["widget_name"])
        else:
            logger.warning(
                f"[WidgetResolver] Layout references widget_id={wid} "
                "but it's not in widget_catalog"
            )

    return names, catalog
