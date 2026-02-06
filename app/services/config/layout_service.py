"""
LayoutService - Resolves dashboard layout configuration
Determines which widgets and filters are enabled for a tenant/role
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.config_repository import ConfigRepository
from app.core.cache import metadata_cache


@dataclass
class LayoutConfig:
    """Parsed layout configuration"""
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
    """Widget with full metadata from catalog"""
    widget_id: int
    widget_name: str
    description: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "widget_id": self.widget_id,
            "widget_name": self.widget_name,
            "description": self.description
        }


@dataclass
class ResolvedFilter:
    """Filter with full metadata from DB + configuration from registry"""
    filter_id: int
    filter_name: str
    description: str
    display_order: int
    additional_filter: Optional[Dict[str, Any]] = None
    
    @property
    def config(self):
        """Get filter configuration from registry"""
        from app.services.filters.filter_config import get_filter_config
        return get_filter_config(self.filter_id)
    
    @property
    def filter_type(self) -> str:
        """Get filter type from registry"""
        cfg = self.config
        if cfg:
            return cfg.filter_type.value
        return "dropdown"
    
    @property
    def options_source(self) -> Optional[str]:
        """Get options source from registry"""
        cfg = self.config
        if cfg and cfg.options_source:
            return cfg.options_source.value
        return None
    
    @property
    def static_options(self) -> Optional[List[Dict]]:
        """Get static options from registry (for dropdown/select with fixed options)"""
        cfg = self.config
        if cfg:
            return cfg.static_options
        return None
    
    @property
    def param_name(self) -> str:
        """Get API parameter name from registry"""
        cfg = self.config
        if cfg:
            return cfg.param_name
        return f"filter_{self.filter_id}"
    
    @property
    def default_value(self) -> Any:
        """Get default value from registry"""
        cfg = self.config
        if cfg:
            return cfg.default_value
        return None
    
    @property
    def placeholder(self) -> str:
        """Get placeholder text from registry"""
        cfg = self.config
        if cfg:
            return cfg.placeholder
        return ""
    
    @property
    def depends_on(self) -> Optional[int]:
        """Get dependency from registry"""
        cfg = self.config
        if cfg:
            return cfg.depends_on
        return None
    
    @property
    def line_groups(self) -> Optional[List[Dict]]:
        """Get line groupings from additional_filter (for production_line filter)"""
        if self.additional_filter is None:
            return None
        # Support for grouped lines like {"alias": "Fraccionado", "line_ids":[2,3,4]}
        if "line_ids" in self.additional_filter:
            return [self.additional_filter]
        return self.additional_filter.get("groups")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "filter_id": self.filter_id,
            "filter_name": self.filter_name,
            "description": self.description,
            "display_order": self.display_order,
            "filter_type": self.filter_type,
            "options_source": self.options_source,
            "static_options": self.static_options,
            "param_name": self.param_name,
            "default_value": self.default_value,
            "placeholder": self.placeholder,
            "depends_on": self.depends_on,
            "line_groups": self.line_groups,
            "additional_filter": self.additional_filter or {}
        }


class LayoutService:
    """
    Service for resolving dashboard layout configurations.
    
    Flow:
    1. Get layout_config from DASHBOARD_TEMPLATE by tenant_id + role
    2. Parse JSON to extract widget_ids and filter_ids
    3. Resolve full widget/filter metadata from cache or DB
    """
    
    @staticmethod
    async def get_layout_config(
        global_session: AsyncSession,
        tenant_id: int,
        role: str
    ) -> Optional[LayoutConfig]:
        """
        Get and parse layout configuration for a tenant/role.
        
        Args:
            global_session: AsyncSession for global database
            tenant_id: Tenant ID
            role: User role (ADMIN, MANAGER, VIEWER)
            
        Returns:
            LayoutConfig object or None if no template exists
        """
        raw_config = await ConfigRepository.get_layout_config(
            global_session, tenant_id, role
        )
        
        if raw_config is None:
            return None
        
        # Parse widget and filter IDs from layout_config JSON
        # Expected format: {"widgets": [1, 2, 3], "filters": [1, 2]}
        widget_ids = raw_config.get("widgets", [])
        filter_ids = raw_config.get("filters", [])
        
        return LayoutConfig(
            tenant_id=tenant_id,
            role=role,
            enabled_widget_ids=widget_ids,
            enabled_filter_ids=filter_ids,
            raw_config=raw_config
        )
    
    @staticmethod
    def resolve_widgets_from_cache(
        widget_ids: List[int]
    ) -> List[ResolvedWidget]:
        """
        Resolve widget metadata from cache.
        Uses MetadataCache for fast lookups without DB queries.
        
        Args:
            widget_ids: List of widget IDs to resolve
            
        Returns:
            List of ResolvedWidget objects
        """
        resolved = []
        widget_catalog = metadata_cache.get_widget_catalog()
        
        for wid in widget_ids:
            widget_data = widget_catalog.get(wid)
            if widget_data:
                resolved.append(ResolvedWidget(
                    widget_id=wid,
                    widget_name=widget_data["widget_name"],
                    description=widget_data["description"]
                ))
        
        return resolved
    
    @staticmethod
    def resolve_filters_from_cache(
        filter_ids: List[int]
    ) -> List[ResolvedFilter]:
        """
        Resolve filter metadata from cache.
        Uses MetadataCache for fast lookups without DB queries.
        
        Args:
            filter_ids: List of filter IDs to resolve
            
        Returns:
            List of ResolvedFilter objects ordered by display_order
        """
        resolved = []
        filters = metadata_cache.get_filters()
        
        for fid in filter_ids:
            filter_data = filters.get(fid)
            if filter_data:
                resolved.append(ResolvedFilter(
                    filter_id=fid,
                    filter_name=filter_data["filter_name"],
                    description=filter_data["description"],
                    display_order=filter_data["display_order"],
                    additional_filter=filter_data.get("additional_filter", {})
                ))
        
        # Sort by display_order
        resolved.sort(key=lambda f: f.display_order)
        return resolved
    
    @staticmethod
    async def get_resolved_layout(
        global_session: AsyncSession,
        tenant_id: int,
        role: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get complete resolved layout with widget and filter metadata.
        
        This is the main method to call when rendering the dashboard.
        It combines layout_config with full widget/filter details.
        
        Args:
            global_session: AsyncSession for global database
            tenant_id: Tenant ID
            role: User role
            
        Returns:
            Dict with structure:
            {
                "tenant_id": int,
                "role": str,
                "widgets": [{"widget_id": 1, "widget_name": "...", ...}, ...],
                "filters": [{"filter_id": 1, "filter_name": "...", ...}, ...]
            }
        """
        layout = await LayoutService.get_layout_config(
            global_session, tenant_id, role
        )
        
        if layout is None:
            return None
        
        # Resolve from cache
        widgets = LayoutService.resolve_widgets_from_cache(layout.enabled_widget_ids)
        filters = LayoutService.resolve_filters_from_cache(layout.enabled_filter_ids)
        
        return {
            "tenant_id": tenant_id,
            "role": role,
            "widgets": [w.to_dict() for w in widgets],
            "filters": [f.to_dict() for f in filters]
        }
    
    @staticmethod
    def is_widget_enabled(layout: LayoutConfig, widget_id: int) -> bool:
        """Check if a specific widget is enabled in the layout"""
        return widget_id in layout.enabled_widget_ids
    
    @staticmethod
    def is_filter_enabled(layout: LayoutConfig, filter_id: int) -> bool:
        """Check if a specific filter is enabled in the layout"""
        return filter_id in layout.enabled_filter_ids
