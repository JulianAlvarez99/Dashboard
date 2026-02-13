"""
Tenant Database Models — db_client_{tenant}.

Tables: production_line, area, product, shift, filter,
        failure, incident, system_config.

Dynamic tables per line (not mapped as ORM models):
  detection_line_{line_name}
  downtime_events_{line_name}
"""

from datetime import datetime, time
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey, Integer,
    Numeric, String, JSON, Time, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from new_app.core.database import TenantBase


class ProductionLine(TenantBase):
    """Production line with performance & downtime config."""
    __tablename__ = "production_line"

    line_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    line_name: Mapped[str] = mapped_column(String(100), nullable=False)
    line_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    availability: Mapped[int] = mapped_column(Integer, default=0)
    performance: Mapped[int] = mapped_column(Integer, default=0)
    downtime_threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    auto_detect_downtime: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )

    areas: Mapped[List["Area"]] = relationship(back_populates="production_line")


class Area(TenantBase):
    """Detection area within a production line (input / output / process)."""
    __tablename__ = "area"

    area_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    line_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("production_line.line_id"), nullable=False
    )
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

    production_line: Mapped["ProductionLine"] = relationship(back_populates="areas")


class Product(TenantBase):
    """Product catalogue."""
    __tablename__ = "product"

    product_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_name: Mapped[str] = mapped_column(String(100), nullable=False)
    product_code: Mapped[str] = mapped_column(String(50), nullable=False)
    product_weight: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    product_color: Mapped[str] = mapped_column(String(10), nullable=False)
    production_std: Mapped[int] = mapped_column(Integer, nullable=False)
    product_per_batch: Mapped[int] = mapped_column(Integer, nullable=False)


class Shift(TenantBase):
    """Work-shift schedule."""
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
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )


class Filter(TenantBase):
    """
    Client-specific filter definition.

    ``filter_name`` contains the **class name** of the Python filter
    to be instantiated via the Registry Pattern (e.g., "DateRangeFilter",
    "DropdownFilter").

    ``additional_filter`` stores JSON overrides — e.g. line groupings:
        {"alias": "Fraccionado", "line_ids": [2, 3, 4]}
    """
    __tablename__ = "filter"

    filter_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filter_name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    filter_status: Mapped[bool] = mapped_column(Boolean, default=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    additional_filter: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )


class Failure(TenantBase):
    """Failure-type catalogue."""
    __tablename__ = "failure"

    failure_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type_failure: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(100), nullable=False)


class Incident(TenantBase):
    """Incidents linked to a failure type."""
    __tablename__ = "incident"

    incident_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    failure_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("failure.failure_id"), nullable=False
    )
    incident_code: Mapped[str] = mapped_column(String(10), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    has_solution: Mapped[bool] = mapped_column(Boolean, nullable=False)
    solution: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class SystemConfig(TenantBase):
    """Key-value configuration store per tenant."""
    __tablename__ = "system_config"

    config_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[dict] = mapped_column(JSON, nullable=False)
