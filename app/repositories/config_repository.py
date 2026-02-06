"""
ConfigRepository - Data access for configuration tables
Handles DashboardTemplate, WidgetCatalog, Filter queries
"""

from typing import List, Optional, Dict, Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.global_models import DashboardTemplate, WidgetCatalog, User, Tenant
from app.models.tenant_models import Filter


class ConfigRepository:
    """
    Repository for configuration-related database operations.
    Handles both global and tenant database queries.
    """
    
    # === Dashboard Template Operations (Global DB) ===
    
    @staticmethod
    async def get_dashboard_template(
        session: AsyncSession,
        tenant_id: int,
        role: str
    ) -> Optional[DashboardTemplate]:
        """
        Get dashboard template for a specific tenant and role.
        Returns None if no template exists.
        Role comparison is case-insensitive.
        """
        from sqlalchemy import func
        stmt = select(DashboardTemplate).where(
            DashboardTemplate.tenant_id == tenant_id,
            func.lower(DashboardTemplate.role_access) == role.lower()
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_layout_config(
        session: AsyncSession,
        tenant_id: int,
        role: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get just the layout_config JSON for a tenant/role.
        Returns the parsed JSON dict or None.
        """
        template = await ConfigRepository.get_dashboard_template(session, tenant_id, role)
        if template:
            return template.layout_config
        return None
    
    @staticmethod
    async def get_all_templates_for_tenant(
        session: AsyncSession,
        tenant_id: int
    ) -> List[DashboardTemplate]:
        """Get all dashboard templates for a tenant"""
        stmt = select(DashboardTemplate).where(
            DashboardTemplate.tenant_id == tenant_id
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
    
    # === Widget Catalog Operations (Global DB) ===
    
    @staticmethod
    async def get_all_widgets(session: AsyncSession) -> List[WidgetCatalog]:
        """Get all available widgets from catalog"""
        stmt = select(WidgetCatalog).order_by(WidgetCatalog.widget_id)
        result = await session.execute(stmt)
        return list(result.scalars().all())
    
    @staticmethod
    async def get_widget_by_id(
        session: AsyncSession,
        widget_id: int
    ) -> Optional[WidgetCatalog]:
        """Get a specific widget by ID"""
        stmt = select(WidgetCatalog).where(WidgetCatalog.widget_id == widget_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_widgets_by_ids(
        session: AsyncSession,
        widget_ids: List[int]
    ) -> List[WidgetCatalog]:
        """Get multiple widgets by their IDs"""
        if not widget_ids:
            return []
        stmt = select(WidgetCatalog).where(
            WidgetCatalog.widget_id.in_(widget_ids)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
    
    # === Filter Operations (Tenant DB) ===
    
    @staticmethod
    async def get_all_filters(session: AsyncSession) -> List[Filter]:
        """Get all active filters ordered by display_order"""
        stmt = select(Filter).where(
            Filter.filter_status == True
        ).order_by(Filter.display_order)
        result = await session.execute(stmt)
        return list(result.scalars().all())
    
    @staticmethod
    async def get_filter_by_id(
        session: AsyncSession,
        filter_id: int
    ) -> Optional[Filter]:
        """Get a specific filter by ID"""
        stmt = select(Filter).where(Filter.filter_id == filter_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_filters_by_ids(
        session: AsyncSession,
        filter_ids: List[int]
    ) -> List[Filter]:
        """Get multiple filters by their IDs, maintaining display_order"""
        if not filter_ids:
            return []
        stmt = select(Filter).where(
            Filter.filter_id.in_(filter_ids)
        ).order_by(Filter.display_order)
        result = await session.execute(stmt)
        return list(result.scalars().all())
    
    # === User Operations (Global DB) ===
    
    @staticmethod
    async def get_user_by_username(
        session: AsyncSession,
        username: str
    ) -> Optional[User]:
        """Get user by username"""
        stmt = select(User).where(User.username == username)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_user_by_id(
        session: AsyncSession,
        user_id: int
    ) -> Optional[User]:
        """Get user by ID"""
        stmt = select(User).where(User.user_id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    
    # === Tenant Operations (Global DB) ===
    
    @staticmethod
    async def get_tenant_by_id(
        session: AsyncSession,
        tenant_id: int
    ) -> Optional[Tenant]:
        """Get tenant by ID"""
        stmt = select(Tenant).where(Tenant.tenant_id == tenant_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
