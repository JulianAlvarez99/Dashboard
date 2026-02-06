"""
Tenant/Client Database Models
Models for client databases: ProductionLine, Area, Product, Shift, Filter, etc.
"""

from datetime import datetime, time
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey, Integer,
    String, Text, JSON, Time, Numeric, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import TenantBase


class ProductionLine(TenantBase):
    """Production lines"""
    __tablename__ = "production_line"
    
    line_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    line_name: Mapped[str] = mapped_column(String(100), nullable=False)
    line_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    availability: Mapped[int] = mapped_column(Integer, default=0)
    performance: Mapped[int] = mapped_column(Integer, default=0)
    downtime_threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    
    # Relationships
    areas: Mapped[List["Area"]] = relationship(back_populates="production_line")


class Area(TenantBase):
    """Detection areas within a production line"""
    __tablename__ = "area"
    
    area_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    line_id: Mapped[int] = mapped_column(Integer, ForeignKey("production_line.line_id"), nullable=False)
    area_name: Mapped[str] = mapped_column(String(50), nullable=False)
    area_type: Mapped[str] = mapped_column(String(20), nullable=False)
    area_order: Mapped[int] = mapped_column(Integer, nullable=False)
    coord_x1: Mapped[int] = mapped_column(Integer, nullable=False)
    coord_y1: Mapped[int] = mapped_column(Integer, nullable=False)
    coord_x2: Mapped[int] = mapped_column(Integer, nullable=False)
    coord_y2: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    
    # Relationships
    production_line: Mapped["ProductionLine"] = relationship(back_populates="areas")


class Product(TenantBase):
    """Product catalog"""
    __tablename__ = "product"
    
    product_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_name: Mapped[str] = mapped_column(String(100), nullable=False)
    product_code: Mapped[str] = mapped_column(String(50), nullable=False)
    product_weight: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    product_color: Mapped[str] = mapped_column(String(10), nullable=False)
    production_std: Mapped[int] = mapped_column(Integer, nullable=False)
    product_per_batch: Mapped[int] = mapped_column(Integer, nullable=False)


class Shift(TenantBase):
    """Work shifts configuration"""
    __tablename__ = "shift"
    
    shift_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shift_name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    shift_status: Mapped[bool] = mapped_column(Boolean, default=True)
    days_implemented: Mapped[dict] = mapped_column(JSON, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    is_overnight: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )


class Filter(TenantBase):
    """Available filters for the client"""
    __tablename__ = "filter"
    
    filter_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filter_name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    filter_status: Mapped[bool] = mapped_column(Boolean, default=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    additional_filter: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )


class Failure(TenantBase):
    """Failure types catalog"""
    __tablename__ = "failure"
    
    failure_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type_failure: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(100), nullable=False)


class Incident(TenantBase):
    """Incident records"""
    __tablename__ = "incident"
    
    incident_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    failure_id: Mapped[int] = mapped_column(Integer, ForeignKey("failure.failure_id"), nullable=False)
    incident_code: Mapped[str] = mapped_column(String(10), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    has_solution: Mapped[bool] = mapped_column(Boolean, nullable=False)
    solution: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class SystemConfig(TenantBase):
    """Key-value configuration store"""
    __tablename__ = "system_config"
    
    config_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[dict] = mapped_column(JSON, nullable=False)
