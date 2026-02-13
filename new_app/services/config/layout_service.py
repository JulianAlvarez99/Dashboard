"""
LayoutService — Resolves dashboard layout from ``dashboard_template``.

Reads ``layout_config`` JSON per (tenant_id, role) and resolves
which widgets and filters the user should see on their dashboard.

``layout_config`` format::

    {
        "widgets": [1, 2, 3, 4, 5],   # → widget_catalog.widget_id
        "filters": [1, 2, 3]           # → filter.filter_id (tenant DB)
    }

Usage::

    from new_app.services.config.layout_service import layout_service

    config = await layout_service.get_layout(tenant_id=1, role="ADMIN")
    # config = {
    #   "tenant_id": 1, "role": "ADMIN",
    #   "widgets": [...], "filters": [...],
    #   "enabled_widget_ids": [1,2,3], "enabled_filter_ids": [1,2]
    # }
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select

from new_app.core.cache import metadata_cache
from new_app.core.database import db_manager
from new_app.models.global_models import DashboardTemplate


# ── Dataclasses ──────────────────────────────────────────────────

@dataclass
class LayoutConfig:
    """Parsed layout configuration from dashboard_template."""
    tenant_id: int
    role: str
    enabled_widget_ids: List[int]
    enabled_filter_ids: List[int]
    raw_config: Dict[str, Any]

    @property
    def has_widgets(self) -> bool:
        return len(self.enabled_widget_ids) > 0

    @property
    def has_filters(self) -> bool:
        return len(self.enabled_filter_ids) > 0


@dataclass
class ResolvedWidget:
    """Widget with full metadata from widget_catalog cache."""
    widget_id: int
    widget_name: str
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "widget_id": self.widget_id,
            "widget_name": self.widget_name,
            "description": self.description,
        }


# ── Service ──────────────────────────────────────────────────────

class LayoutService:
    """
    Resolves dashboard layout configurations.

    Pipeline:
      1. Query ``dashboard_template`` for (tenant_id, role)
      2. Parse ``layout_config`` JSON → lists of IDs
      3. Resolve widget metadata from ``widget_catalog`` cache
      4. Return filter IDs for FilterEngine to whitelist
    """

    async def get_layout_config(
        self,
        tenant_id: int,
        role: str,
    ) -> Optional[LayoutConfig]:
        """
        Load layout_config from DB by (tenant_id, role).

        Returns ``None`` if no template row exists.
        """
        async with db_manager.get_global_session() as session:
            stmt = select(DashboardTemplate).where(
                DashboardTemplate.tenant_id == tenant_id,
                func.lower(DashboardTemplate.role_access) == role.lower(),
            )
            result = await session.execute(stmt)
            template = result.scalar_one_or_none()

        if template is None:
            return None

        raw = template.layout_config or {}
        return LayoutConfig(
            tenant_id=tenant_id,
            role=role,
            enabled_widget_ids=raw.get("widgets", []),
            enabled_filter_ids=raw.get("filters", []),
            raw_config=raw,
        )

    def resolve_widgets(
        self,
        widget_ids: List[int],
    ) -> List[ResolvedWidget]:
        """
        Resolve widget IDs → full metadata from widget_catalog cache.

        Preserves the order specified in ``widget_ids``.
        """
        catalog = metadata_cache.get_widget_catalog()
        resolved = []
        for wid in widget_ids:
            data = catalog.get(wid)
            if data:
                resolved.append(ResolvedWidget(
                    widget_id=wid,
                    widget_name=data["widget_name"],
                    description=data["description"],
                ))
            else:
                print(f"[LayoutService] WARN: widget_id={wid} not in cache")
        return resolved

    async def get_resolved_layout(
        self,
        tenant_id: int,
        role: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Full pipeline: load config → resolve widgets → return dict.

        Returns::

            {
                "tenant_id": 1,
                "role": "ADMIN",
                "enabled_widget_ids": [1, 2, 3],
                "enabled_filter_ids": [1, 2],
                "widgets": [{"widget_id": 1, "widget_name": "...", ...}, ...],
            }

        Returns ``None`` if no template exists for this tenant+role.
        """
        config = await self.get_layout_config(tenant_id, role)
        if config is None:
            return None

        widgets = self.resolve_widgets(config.enabled_widget_ids)

        return {
            "tenant_id": config.tenant_id,
            "role": config.role,
            "enabled_widget_ids": config.enabled_widget_ids,
            "enabled_filter_ids": config.enabled_filter_ids,
            "widgets": [w.to_dict() for w in widgets],
        }


# ── Singleton ────────────────────────────────────────────────────
layout_service = LayoutService()
