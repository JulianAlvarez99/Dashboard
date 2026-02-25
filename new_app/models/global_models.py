"""
Global Database Models — camet_global.

Tables: tenant, user, widget_catalog, dashboard_template,
        user_login, audit_log, user_query.
"""

from datetime import date, datetime, time
from typing import List, Optional

from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, ForeignKey, Integer,
    String, JSON, Text, Time, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from new_app.core.database import GlobalBase


class Tenant(GlobalBase):
    """Registered client company."""
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
    dashboard_templates: Mapped[List["DashboardTemplate"]] = relationship(
        back_populates="tenant"
    )


class User(GlobalBase):
    """System user linked to a tenant."""
    __tablename__ = "user"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenant.tenant_id"), nullable=False
    )
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    permissions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="users")


class WidgetCatalog(GlobalBase):
    """Global widget registry.

    ``widget_name`` holds the exact Python class name to instantiate
    at runtime via the Registry Pattern.
    """
    __tablename__ = "widget_catalog"

    widget_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    widget_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)


class DashboardTemplate(GlobalBase):
    """Layout configuration per tenant + role."""
    __tablename__ = "dashboard_template"

    template_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenant.tenant_id"), nullable=False
    )
    role_access: Mapped[str] = mapped_column(String(50), nullable=False)
    layout_config: Mapped[dict] = mapped_column(JSON, nullable=False)

    tenant: Mapped["Tenant"] = relationship(back_populates="dashboard_templates")


class UserLogin(GlobalBase):
    """Login session audit trail."""
    __tablename__ = "user_login"

    login_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("user.user_id"), nullable=False
    )
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
    """Security / action audit log.

    ``user_id = 0`` is the convention for anonymous/unknown users
    (e.g. a login attempt where the username was not found in the DB).
    This avoids a migration to make user_id nullable.
    """
    __tablename__ = "audit_log"

    log_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("user.user_id"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False)  # JSON-serialised dict
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )


class UserQuery(GlobalBase):
    """Dashboard query activity log.

    Maps to the existing ``user_query`` table in camet_global.

    IMPORTANT: The column ``slq_query`` has a typo in the DB
    (should be ``sql_query``).  The name is intentionally kept verbatim
    to avoid a migration.  Do NOT rename it.
    """
    __tablename__ = "user_query"

    query_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("user.user_id"), nullable=False
    )
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    slq_query: Mapped[str] = mapped_column(Text, nullable=False)          # typo in DB — kept
    query_parameters: Mapped[str] = mapped_column(Text, nullable=False)   # JSON string
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    line: Mapped[str] = mapped_column(String(20), nullable=False)
    interval_type: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
