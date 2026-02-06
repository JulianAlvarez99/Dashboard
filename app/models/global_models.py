"""
Global Database Models
Models for Camet_Global database: Tenant, User, WidgetCatalog, DashboardTemplate
"""

from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey, Integer, 
    String, Text, JSON, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import GlobalBase


class Tenant(GlobalBase):
    """Tenant/Client company"""
    __tablename__ = "tenant"
    
    tenant_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_name: Mapped[str] = mapped_column(String(100), nullable=False)
    associated_since: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    config_tenant: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    # Relationships
    users: Mapped[List["User"]] = relationship(back_populates="tenant")
    dashboard_templates: Mapped[List["DashboardTemplate"]] = relationship(back_populates="tenant")


class User(GlobalBase):
    """System users - linked to a tenant"""
    __tablename__ = "user"
    
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenant.tenant_id"), nullable=False)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    permissions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    
    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="users")


class WidgetCatalog(GlobalBase):
    """Available widgets in the system"""
    __tablename__ = "widget_catalog"
    
    widget_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    widget_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)


class DashboardTemplate(GlobalBase):
    """Dashboard layout configuration per tenant/role"""
    __tablename__ = "dashboard_template"
    
    template_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenant.tenant_id"), nullable=False)
    role_access: Mapped[str] = mapped_column(String(50), nullable=False)
    layout_config: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="dashboard_templates")


class UserLogin(GlobalBase):
    """Login session history"""
    __tablename__ = "user_login"
    
    login_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.user_id"), nullable=False)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    user_agent: Mapped[str] = mapped_column(String(255), nullable=False)
    login_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    logout_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )


class AuditLog(GlobalBase):
    """Security audit log"""
    __tablename__ = "audit_log"
    
    log_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.user_id"), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
