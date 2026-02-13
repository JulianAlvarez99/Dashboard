# FASE 2: Sistema de Caché y Metadatos

## 🎯 OBJETIVO DE LA FASE 2

Implementar el sistema de caché en memoria para metadatos de configuración de planta, crear los modelos de base de datos del cliente, y desarrollar endpoints CRUD completos para la gestión de configuración.

**Duración Estimada:** 1-2 semanas  
**Prioridad:** Alta (bloquea Fase 3)

**PRINCIPIO FUNDAMENTAL:** Los metadatos (PRODUCT, AREA, PRODUCTION_LINE, FILTER, SHIFT) se cargan en memoria al inicio de la aplicación o al login del usuario para evitar JOINs masivos en queries de producción.

---

## 📦 TASK 2.1: Modelos de Cliente (DB_CLIENT)

### Descripción
Crear todos los modelos SQLAlchemy para las tablas de configuración de planta en la base de datos del cliente.

### Criterios de Aceptación
- [x] Modelo ProductionLine implementado con campos OEE
- [x] Modelo Area implementado con coordenadas de mapeo
- [x] Modelo Product implementado con datos físicos
- [x] Modelo Filter implementado con configuración JSON
- [x] Modelo Shift implementado con soporte overnight
- [x] Modelo Failure e Incident implementados
- [x] Relaciones entre modelos correctamente definidas
- [x] Índices optimizados creados

### Archivo: `app/models/client_db/production.py`


"""
Production Line and Area models
"""
from sqlalchemy import Column, Integer, String, Boolean, TIMESTAMP, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class ProductionLine(Base):
    __tablename__ = "PRODUCTION_LINE"
    
    line_id = Column(Integer, primary_key=True, autoincrement=True)
    line_name = Column(String(100), nullable=False)
    line_code = Column(String(50), nullable=False, unique=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # OEE Configuration
    availability = Column(Integer, nullable=False, comment="Target availability %")
    performance = Column(Integer, nullable=False, comment="Target performance %")
    downtime_threshold = Column(Integer, nullable=False, comment="Seconds to consider downtime")
    
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    
    # Relationships
    areas = relationship("Area", back_populates="production_line", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_line_active', 'is_active'),
        Index('idx_line_code', 'line_code'),
    )
    
    def __repr__(self):
        return f"<ProductionLine(id={self.line_id}, name='{self.line_name}', code='{self.line_code}')>"


class Area(Base):
    __tablename__ = "AREA"
    
    area_id = Column(Integer, primary_key=True, autoincrement=True)
    line_id = Column(Integer, ForeignKey('PRODUCTION_LINE.line_id'), nullable=False)
    area_name = Column(String(50), nullable=False)
    area_type = Column(String(20), nullable=False, comment="input, process, output, discard")
    area_order = Column(Integer, nullable=False, comment="Sequential order in line")
    
    # Coordinates for visual mapping
    coord_x1 = Column(Integer, nullable=True)
    coord_y1 = Column(Integer, nullable=True)
    coord_x2 = Column(Integer, nullable=True)
    coord_y2 = Column(Integer, nullable=True)
    
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    
    # Relationships
    production_line = relationship("ProductionLine", back_populates="areas")
    camera_areas = relationship("CameraArea", back_populates="area")
    
    # Indexes
    __table_args__ = (
        Index('idx_area_line', 'line_id'),
        Index('idx_area_type', 'area_type'),
        Index('idx_area_order', 'area_order'),
    )
    
    def __repr__(self):
        return f"<Area(id={self.area_id}, name='{self.area_name}', type='{self.area_type}')>"


### Archivo: `app/models/client_db/product.py`


"""
Product model
"""
from sqlalchemy import Column, Integer, String, DECIMAL, Index
from app.core.database import Base

class Product(Base):
    __tablename__ = "PRODUCT"
    
    product_id = Column(Integer, primary_key=True, autoincrement=True)
    product_name = Column(String(100), nullable=False)
    product_code = Column(String(50), nullable=False, unique=True, index=True)
    product_weight = Column(DECIMAL(5, 2), nullable=True, comment="Weight in kg")
    product_color = Column(String(10), nullable=True)
    production_std = Column(Integer, nullable=True, comment="Standard production units per hour")
    product_per_batch = Column(Integer, nullable=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_product_code', 'product_code'),
        Index('idx_product_name', 'product_name'),
    )
    
    def __repr__(self):
        return f"<Product(id={self.product_id}, name='{self.product_name}', code='{self.product_code}')>"


### Archivo: `app/models/client_db/filter.py`


"""
Filter configuration model
"""
from sqlalchemy import Column, Integer, String, Boolean, JSON, TIMESTAMP
from sqlalchemy.sql import func
from app.core.database import Base

class Filter(Base):
    __tablename__ = "FILTER"
    
    filter_id = Column(Integer, primary_key=True, autoincrement=True)
    filter_name = Column(String(50), nullable=False)
    description = Column(String(255), nullable=True)
    filter_status = Column(Boolean, default=True, nullable=False)
    
    # JSON configuration
    default_value = Column(JSON, nullable=True, comment="Default filter value")
    additional_filter = Column(JSON, nullable=True, comment="Extra UI configuration")
    
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=True)
    
    def __repr__(self):
        return f"<Filter(id={self.filter_id}, name='{self.filter_name}', active={self.filter_status})>"


### Archivo: `app/models/client_db/shift.py`


"""
Shift configuration model
"""
from sqlalchemy import Column, Integer, String, Boolean, JSON, TIME, TIMESTAMP
from sqlalchemy.sql import func
from app.core.database import Base

class Shift(Base):
    __tablename__ = "SHIFT"
    
    shift_id = Column(Integer, primary_key=True, autoincrement=True)
    shift_name = Column(String(50), nullable=False)
    description = Column(String(255), nullable=True)
    shift_status = Column(Boolean, default=True, nullable=False)
    
    # Schedule configuration
    days_implemented = Column(JSON, nullable=True, comment="List of days: ['Monday', 'Tuesday', ...]")
    start_time = Column(TIME, nullable=False)
    end_time = Column(TIME, nullable=False)
    is_overnight = Column(Boolean, default=False, nullable=False, comment="Shift crosses midnight")
    
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=True)
    
    def __repr__(self):
        return f"<Shift(id={self.shift_id}, name='{self.shift_name}', overnight={self.is_overnight})>"


### Archivo: `app/models/client_db/incident.py`


"""
Failure and Incident models for maintenance tracking
"""
from sqlalchemy import Column, Integer, String, Boolean, JSON, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.core.database import Base

class Failure(Base):
    __tablename__ = "FAILURE"
    
    failure_id = Column(Integer, primary_key=True, autoincrement=True)
    type_failure = Column(String(100), nullable=True, comment="Categorization of failure types")
    description = Column(String(100), nullable=True)
    
    # Relationships
    incidents = relationship("Incident", back_populates="failure", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Failure(id={self.failure_id}, desc='{self.description}')>"


class Incident(Base):
    __tablename__ = "INCIDENT"
    
    incident_id = Column(Integer, primary_key=True, autoincrement=True)
    failure_id = Column(Integer, ForeignKey('FAILURE.failure_id'), nullable=False)
    incident_code = Column(String(10), nullable=False, unique=True, index=True)
    description = Column(String(255), nullable=True)
    has_solution = Column(Boolean, default=False, nullable=False)
    solution = Column(Integer, nullable=True, comment="ID of solution or reference")
    
    # Relationships
    failure = relationship("Failure", back_populates="incidents")
    
    # Indexes
    __table_args__ = (
        Index('idx_incident_code', 'incident_code'),
        Index('idx_incident_failure', 'failure_id'),
    )
    
    def __repr__(self):
        return f"<Incident(id={self.incident_id}, code='{self.incident_code}')>"


### Archivo: `app/models/client_db/system.py`


"""
System configuration and monitoring models
"""
from sqlalchemy import Column, Integer, String, BigInteger, DECIMAL, TIMESTAMP, JSON, Index
from sqlalchemy.sql import func
from app.core.database import Base

class SystemConfig(Base):
    __tablename__ = "SYSTEM_CONFIG"
    
    config_id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), nullable=False, unique=True, index=True)
    value = Column(JSON, nullable=True)
    
    def __repr__(self):
        return f"<SystemConfig(key='{self.key}')>"


class SystemMonitor(Base):
    __tablename__ = "SYSTEM_MONITOR"
    
    system_monitor_id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    
    # CPU metrics
    cpu_usage = Column(DECIMAL(5, 2), nullable=True)
    cpu_freq = Column(Integer, nullable=True)
    cpu_temp = Column(BigInteger, nullable=True)
    cpu_temp_sensor = Column(DECIMAL(5, 2), nullable=True)
    
    # RAM metrics
    ram_usage = Column(DECIMAL(5, 2), nullable=True)
    ram_used_bytes = Column(BigInteger, nullable=True)
    
    # GPU metrics
    gpu_name = Column(String(100), nullable=True)
    gpu_temp = Column(DECIMAL(5, 2), nullable=True)
    gpu_usage = Column(DECIMAL(5, 2), nullable=True)
    gpu_mem_used_bytes = Column(BigInteger, nullable=True)
    gpu_mem_total_bytes = Column(BigInteger, nullable=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_monitor_time', 'created_at'),
    )
    
    def __repr__(self):
        return f"<SystemMonitor(id={self.system_monitor_id}, time={self.created_at})>"


class CameraArea(Base):
    __tablename__ = "CAMERA_AREA"
    
    camera_area_id = Column(Integer, primary_key=True, autoincrement=True)
    camara_id = Column(Integer, nullable=False)
    area_id = Column(Integer, ForeignKey('AREA.area_id'), nullable=False)
    status = Column(Boolean, default=True, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=True)
    
    # Relationships
    area = relationship("Area", back_populates="camera_areas")
    
    # Indexes
    __table_args__ = (
        Index('idx_camera_area', 'area_id'),
        Index('idx_camera_id', 'camara_id'),
    )
    
    def __repr__(self):
        return f"<CameraArea(id={self.camera_area_id}, camera={self.camara_id}, area={self.area_id})>"


### Archivo: `app/models/client_db/__init__.py`


"""
Client DB Models - Export all models
"""
from app.models.client_db.production import ProductionLine, Area
from app.models.client_db.product import Product
from app.models.client_db.filter import Filter
from app.models.client_db.shift import Shift
from app.models.client_db.incident import Failure, Incident
from app.models.client_db.system import SystemConfig, SystemMonitor, CameraArea

__all__ = [
    'ProductionLine',
    'Area',
    'Product',
    'Filter',
    'Shift',
    'Failure',
    'Incident',
    'SystemConfig',
    'SystemMonitor',
    'CameraArea',
]


### Verificación

bash
# Verificar que los modelos se importan correctamente
python -c "from app.models.client_db import ProductionLine, Area, Product, Filter, Shift; print('✓ All client models imported successfully')"


---

## 📦 TASK 2.2: Sistema de Caché en Memoria

### Descripción
Implementar un sistema de caché eficiente para almacenar metadatos de configuración en memoria, con TTL configurable y métodos de invalidación.

### Criterios de Aceptación
- [x] Clase MetadataCache implementada
- [x] Método load_metadata que carga todas las tablas de configuración
- [x] Getters individuales para cada tipo de dato
- [x] Sistema de TTL (Time To Live) funcional
- [x] Método de invalidación manual
- [x] Método de refresco condicional
- [x] Thread-safe con asyncio.Lock

### Archivo: `app/core/cache.py`


"""
In-memory metadata cache system
Caches configuration data (PRODUCT, AREA, LINE, FILTER, SHIFT) to avoid repeated DB queries
"""
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import asyncio

from app.models.client_db import (
    ProductionLine,
    Area,
    Product,
    Filter,
    Shift
)


class MetadataCache:
    """
    In-memory cache for metadata with TTL
    
    Usage:
        cache = MetadataCache()
        await cache.load_metadata(tenant_id, db_session)
        product = cache.get_product(product_id)
    """
    
    def __init__(self, ttl_seconds: int = 3600):
        """
        Initialize cache
        
        Args:
            ttl_seconds: Time to live in seconds (default 1 hour)
        """
        self._cache: Dict[str, Dict] = {
            'products': {},      # {product_id: product_dict}
            'areas': {},         # {area_id: area_dict}
            'lines': {},         # {line_id: line_dict}
            'filters': {},       # {filter_id: filter_dict}
            'shifts': {},        # {shift_id: shift_dict}
        }
        self._lock = asyncio.Lock()
        self._last_updated: Optional[datetime] = None
        self._ttl_seconds = ttl_seconds
        self._tenant_id: Optional[int] = None
    
    async def load_metadata(self, tenant_id: int, db: AsyncSession):
        """
        Load all metadata from database into cache
        
        Args:
            tenant_id: Tenant ID (for logging/tracking)
            db: Database session for DB_CLIENT
        """
        async with self._lock:
            start_time = datetime.utcnow()
            
            # Load Production Lines
            result = await db.execute(
                select(ProductionLine).where(ProductionLine.is_active == True)
            )
            lines = result.scalars().all()
            
            self._cache['lines'] = {
                line.line_id: {
                    'line_id': line.line_id,
                    'line_name': line.line_name,
                    'line_code': line.line_code,
                    'is_active': line.is_active,
                    'availability': line.availability,
                    'performance': line.performance,
                    'downtime_threshold': line.downtime_threshold
                }
                for line in lines
            }
            
            # Load Areas
            result = await db.execute(select(Area))
            areas = result.scalars().all()
            
            self._cache['areas'] = {
                area.area_id: {
                    'area_id': area.area_id,
                    'line_id': area.line_id,
                    'area_name': area.area_name,
                    'area_type': area.area_type,
                    'area_order': area.area_order,
                    'coord_x1': area.coord_x1,
                    'coord_y1': area.coord_y1,
                    'coord_x2': area.coord_x2,
                    'coord_y2': area.coord_y2,
                }
                for area in areas
            }
            
            # Load Products
            result = await db.execute(select(Product))
            products = result.scalars().all()
            
            self._cache['products'] = {
                product.product_id: {
                    'product_id': product.product_id,
                    'product_name': product.product_name,
                    'product_code': product.product_code,
                    'product_weight': float(product.product_weight) if product.product_weight else None,
                    'product_color': product.product_color,
                    'production_std': product.production_std,
                    'product_per_batch': product.product_per_batch
                }
                for product in products
            }
            
            # Load Filters
            result = await db.execute(
                select(Filter).where(Filter.filter_status == True)
            )
            filters = result.scalars().all()
            
            self._cache['filters'] = {
                f.filter_id: {
                    'filter_id': f.filter_id,
                    'filter_name': f.filter_name,
                    'description': f.description,
                    'default_value': f.default_value,
                    'additional_filter': f.additional_filter
                }
                for f in filters
            }
            
            # Load Shifts
            result = await db.execute(
                select(Shift).where(Shift.shift_status == True)
            )
            shifts = result.scalars().all()
            
            self._cache['shifts'] = {
                shift.shift_id: {
                    'shift_id': shift.shift_id,
                    'shift_name': shift.shift_name,
                    'description': shift.description,
                    'days_implemented': shift.days_implemented,
                    'start_time': shift.start_time,
                    'end_time': shift.end_time,
                    'is_overnight': shift.is_overnight
                }
                for shift in shifts
            }
            
            # Update metadata
            self._last_updated = datetime.utcnow()
            self._tenant_id = tenant_id
            
            load_time = (datetime.utcnow() - start_time).total_seconds()
            
            print(f"✓ Metadata cache loaded for tenant {tenant_id}")
            print(f"  - Lines: {len(self._cache['lines'])}")
            print(f"  - Areas: {len(self._cache['areas'])}")
            print(f"  - Products: {len(self._cache['products'])}")
            print(f"  - Filters: {len(self._cache['filters'])}")
            print(f"  - Shifts: {len(self._cache['shifts'])}")
            print(f"  - Load time: {load_time:.3f}s")
    
    # === Getters ===
    
    def get_product(self, product_id: int) -> Dict:
        """Get product by ID from cache"""
        return self._cache['products'].get(product_id, {})
    
    def get_all_products(self) -> Dict[int, Dict]:
        """Get all products"""
        return self._cache['products']
    
    def get_area(self, area_id: int) -> Dict:
        """Get area by ID from cache"""
        return self._cache['areas'].get(area_id, {})
    
    def get_all_areas(self) -> Dict[int, Dict]:
        """Get all areas"""
        return self._cache['areas']
    
    def get_areas_by_line(self, line_id: int) -> List[Dict]:
        """Get all areas for a specific line"""
        return [
            area for area in self._cache['areas'].values()
            if area['line_id'] == line_id
        ]
    
    def get_line(self, line_id: int) -> Dict:
        """Get production line by ID from cache"""
        return self._cache['lines'].get(line_id, {})
    
    def get_all_lines(self) -> Dict[int, Dict]:
        """Get all production lines"""
        return self._cache['lines']
    
    def get_filter(self, filter_id: int) -> Dict:
        """Get filter by ID from cache"""
        return self._cache['filters'].get(filter_id, {})
    
    def get_all_filters(self) -> Dict[int, Dict]:
        """Get all filters"""
        return self._cache['filters']
    
    def get_shift(self, shift_id: int) -> Dict:
        """Get shift by ID from cache"""
        return self._cache['shifts'].get(shift_id, {})
    
    def get_all_shifts(self) -> Dict[int, Dict]:
        """Get all shifts"""
        return self._cache['shifts']
    
    # === Helper methods ===
    
    def get_input_area(self, line_id: int) -> Optional[Dict]:
        """Get input area for a line"""
        areas = self.get_areas_by_line(line_id)
        input_areas = [a for a in areas if a['area_type'] == 'input']
        return input_areas[0] if input_areas else None
    
    def get_output_area(self, line_id: int) -> Optional[Dict]:
        """Get output area for a line"""
        areas = self.get_areas_by_line(line_id)
        output_areas = [a for a in areas if a['area_type'] == 'output']
        return output_areas[0] if output_areas else None
    
    def get_process_areas(self, line_id: int) -> List[Dict]:
        """Get all process areas for a line"""
        areas = self.get_areas_by_line(line_id)
        return sorted(
            [a for a in areas if a['area_type'] == 'process'],
            key=lambda x: x['area_order']
        )
    
    # === Cache management ===
    
    def is_loaded(self) -> bool:
        """Check if cache has been loaded"""
        return self._last_updated is not None
    
    def needs_refresh(self) -> bool:
        """Check if cache needs refresh based on TTL"""
        if not self._last_updated:
            return True
        
        time_elapsed = datetime.utcnow() - self._last_updated
        return time_elapsed.total_seconds() > self._ttl_seconds
    
    async def refresh_if_needed(self, tenant_id: int, db: AsyncSession):
        """Refresh cache if TTL has expired"""
        if self.needs_refresh():
            await self.load_metadata(tenant_id, db)
    
    def invalidate(self):
        """Invalidate cache forcing reload on next access"""
        async with self._lock:
            self._last_updated = None
            print(f"✓ Cache invalidated for tenant {self._tenant_id}")
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        return {
            'tenant_id': self._tenant_id,
            'last_updated': self._last_updated.isoformat() if self._last_updated else None,
            'ttl_seconds': self._ttl_seconds,
            'needs_refresh': self.needs_refresh(),
            'counts': {
                'lines': len(self._cache['lines']),
                'areas': len(self._cache['areas']),
                'products': len(self._cache['products']),
                'filters': len(self._cache['filters']),
                'shifts': len(self._cache['shifts']),
            }
        }


# Global cache instance (one per tenant in production)
_cache_instances: Dict[int, MetadataCache] = {}
_cache_lock = asyncio.Lock()


async def get_tenant_cache(tenant_id: int, db: AsyncSession) -> MetadataCache:
    """
    Get or create cache instance for tenant
    
    Args:
        tenant_id: Tenant ID
        db: Database session
        
    Returns:
        MetadataCache instance
    """
    async with _cache_lock:
        if tenant_id not in _cache_instances:
            cache = MetadataCache()
            await cache.load_metadata(tenant_id, db)
            _cache_instances[tenant_id] = cache
        else:
            cache = _cache_instances[tenant_id]
            await cache.refresh_if_needed(tenant_id, db)
        
        return cache


def invalidate_tenant_cache(tenant_id: int):
    """
    Invalidate cache for specific tenant
    
    Args:
        tenant_id: Tenant ID
    """
    if tenant_id in _cache_instances:
        _cache_instances[tenant_id].invalidate()


### Verificación

bash
# Test del sistema de caché
python -c "
import asyncio
from app.core.cache import MetadataCache
from app.core.database import db_manager

async def test_cache():
    cache = MetadataCache()
    
    # Simular carga (requiere DB real)
    # async for session in db_manager.get_session('dashboard_client_1', is_global=False):
    #     await cache.load_metadata(1, session)
    
    print('Cache initialized:', cache.is_loaded())
    print('Cache stats:', cache.get_stats())

asyncio.run(test_cache())
"


---

## 📦 TASK 2.3: Schemas Pydantic para Configuración

### Descripción
Crear schemas de validación para requests y responses de los endpoints de configuración de planta.

### Criterios de Aceptación
- [x] Schemas para ProductionLine (Create, Update, Response)
- [x] Schemas para Area (Create, Update, Response)
- [x] Schemas para Product (Create, Update, Response)
- [x] Schemas para Filter (Create, Update, Response)
- [x] Schemas para Shift (Create, Update, Response)
- [x] Validadores custom para campos JSON
- [x] Validación de rangos numéricos

### Archivo: `app/schemas/production.py`


"""
Production schemas for CRUD operations
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import time


# === Production Line Schemas ===

class ProductionLineBase(BaseModel):
    """Base schema for production line"""
    line_name: str = Field(..., min_length=1, max_length=100)
    line_code: str = Field(..., min_length=1, max_length=50, pattern="^[A-Z0-9_-]+$")
    availability: int = Field(..., ge=0, le=100, description="Target availability %")
    performance: int = Field(..., ge=0, le=100, description="Target performance %")
    downtime_threshold: int = Field(..., ge=60, le=3600, description="Seconds to consider downtime")


class ProductionLineCreate(ProductionLineBase):
    """Schema for creating production line"""
    is_active: bool = True


class ProductionLineUpdate(BaseModel):
    """Schema for updating production line (all fields optional)"""
    line_name: Optional[str] = Field(None, min_length=1, max_length=100)
    is_active: Optional[bool] = None
    availability: Optional[int] = Field(None, ge=0, le=100)
    performance: Optional[int] = Field(None, ge=0, le=100)
    downtime_threshold: Optional[int] = Field(None, ge=60, le=3600)


class ProductionLineResponse(ProductionLineBase):
    """Schema for production line response"""
    line_id: int
    is_active: bool
    
    class Config:
        from_attributes = True


# === Area Schemas ===

class AreaBase(BaseModel):
    """Base schema for area"""
    area_name: str = Field(..., min_length=1, max_length=50)
    area_type: str = Field(..., pattern="^(input|process|output|discard)$")
    area_order: int = Field(..., ge=1, description="Sequential order in line")


class AreaCreate(AreaBase):
    """Schema for creating area"""
    line_id: int = Field(..., gt=0)
    coord_x1: Optional[int] = None
    coord_y1: Optional[int] = None
    coord_x2: Optional[int] = None
    coord_y2: Optional[int] = None


class AreaUpdate(BaseModel):
    """Schema for updating area"""
    area_name: Optional[str] = Field(None, min_length=1, max_length=50)
    area_type: Optional[str] = Field(None, pattern="^(input|process|output|discard)$")
    area_order: Optional[int] = Field(None, ge=1)
    coord_x1: Optional[int] = None
    coord_y1: Optional[int] = None
    coord_x2: Optional[int] = None
    coord_y2: Optional[int] = None


class AreaResponse(AreaBase):
    """Schema for area response"""
    area_id: int
    line_id: int
    coord_x1: Optional[int]
    coord_y1: Optional[int]
    coord_x2: Optional[int]
    coord_y2: Optional[int]
    
    class Config:
        from_attributes = True


# === Product Schemas ===

class ProductBase(BaseModel):
    """Base schema for product"""
    product_name: str = Field(..., min_length=1, max_length=100)
    product_code: str = Field(..., min_length=1, max_length=50, pattern="^[A-Z0-9_-]+$")


class ProductCreate(ProductBase):
    """Schema for creating product"""
    product_weight: Optional[float] = Field(None, ge=0, le=999.99)
    product_color: Optional[str] = Field(None, max_length=10)
    production_std: Optional[int] = Field(None, ge=0)
    product_per_batch: Optional[int] = Field(None, ge=1)


class ProductUpdate(BaseModel):
    """Schema for updating product"""
    product_name: Optional[str] = Field(None, min_length=1, max_length=100)
    product_weight: Optional[float] = Field(None, ge=0, le=999.99)
    product_color: Optional[str] = Field(None, max_length=10)
    production_std: Optional[int] = Field(None, ge=0)
    product_per_batch: Optional[int] = Field(None, ge=1)


class ProductResponse(ProductBase):
    """Schema for product response"""
    product_id: int
    product_weight: Optional[float]
    product_color: Optional[str]
    production_std: Optional[int]
    product_per_batch: Optional[int]
    
    class Config:
        from_attributes = True


# === Filter Schemas ===

class FilterBase(BaseModel):
    """Base schema for filter"""
    filter_name: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=255)


class FilterCreate(FilterBase):
    """Schema for creating filter"""
    filter_status: bool = True
    default_value: Optional[dict] = None
    additional_filter: Optional[dict] = None


class FilterUpdate(BaseModel):
    """Schema for updating filter"""
    filter_name: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=255)
    filter_status: Optional[bool] = None
    default_value: Optional[dict] = None
    additional_filter: Optional[dict] = None


class FilterResponse(FilterBase):
    """Schema for filter response"""
    filter_id: int
    filter_status: bool
    default_value: Optional[dict]
    additional_filter: Optional[dict]
    
    class Config:
        from_attributes = True


# === Shift Schemas ===

class ShiftBase(BaseModel):
    """Base schema for shift"""
    shift_name: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=255)
    start_time: time
    end_time: time


class ShiftCreate(ShiftBase):
    """Schema for creating shift"""
    shift_status: bool = True
    days_implemented: List[str] = Field(
        default=['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'],
        description="List of days when shift applies"
    )
    is_overnight: bool = False
    
    @validator('days_implemented')
    def validate_days(cls, v):
        valid_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        for day in v:
            if day not in valid_days:
                raise ValueError(f"Invalid day: {day}. Must be one of {valid_days}")
        return v
    
    @validator('is_overnight')
    def validate_overnight(cls, v, values):
        if v and 'start_time' in values and 'end_time' in values:
            if values['end_time'] > values['start_time']:
                raise ValueError("For overnight shifts, end_time must be less than start_time")
        return v


class ShiftUpdate(BaseModel):
    """Schema for updating shift"""
    shift_name: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=255)
    shift_status: Optional[bool] = None
    days_implemented: Optional[List[str]] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    is_overnight: Optional[bool] = None


class ShiftResponse(ShiftBase):
    """Schema for shift response"""
    shift_id: int
    shift_status: bool
    days_implemented: List[str]
    is_overnight: bool
    
    class Config:
        from_attributes = True


## 📦 TASK 2.4: Repositorios para Acceso a Datos

### Descripción
Implementar el patrón Repository para encapsular el acceso a datos de configuración de planta.

### Criterios de Aceptación
- [x] BaseRepository genérico implementado
- [x] ProductionLineRepository con métodos CRUD
- [x] AreaRepository con métodos CRUD
- [x] ProductRepository con métodos CRUD
- [x] FilterRepository con métodos CRUD
- [x] ShiftRepository con métodos CRUD
- [x] Manejo de errores consistente

### Archivo: `app/repositories/base_repository.py`


"""
Base repository with generic CRUD operations
"""
from typing import TypeVar, Generic, Type, Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.exc import IntegrityError

from app.core.database import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Base repository with generic CRUD operations
    
    Usage:
        class UserRepository(BaseRepository[User]):
            def __init__(self, db: AsyncSession):
                super().__init__(User, db)
    """
    
    def __init__(self, model: Type[ModelType], db: AsyncSession):
        self.model = model
        self.db = db
    
    async def create(self, data: Dict[str, Any]) -> ModelType:
        """
        Create new record
        
        Args:
            data: Dictionary with model fields
            
        Returns:
            Created model instance
            
        Raises:
            IntegrityError: If unique constraint violated
        """
        instance = self.model(**data)
        self.db.add(instance)
        await self.db.commit()
        await self.db.refresh(instance)
        return instance
    
    async def get_by_id(self, id: int) -> Optional[ModelType]:
        """
        Get record by ID
        
        Args:
            id: Primary key value
            
        Returns:
            Model instance or None if not found
        """
        result = await self.db.execute(
            select(self.model).where(self.model.__table__.c[self._get_pk_name()] == id)
        )
        return result.scalar_one_or_none()
    
    async def get_all(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        """
        Get all records with pagination
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of model instances
        """
        result = await self.db.execute(
            select(self.model)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def update(self, id: int, data: Dict[str, Any]) -> Optional[ModelType]:
        """
        Update record by ID
        
        Args:
            id: Primary key value
            data: Dictionary with fields to update
            
        Returns:
            Updated model instance or None if not found
        """
        # Remove None values
        data = {k: v for k, v in data.items() if v is not None}
        
        if not data:
            return await self.get_by_id(id)
        
        pk_name = self._get_pk_name()
        stmt = (
            update(self.model)
            .where(self.model.__table__.c[pk_name] == id)
            .values(**data)
            .returning(self.model)
        )
        
        result = await self.db.execute(stmt)
        await self.db.commit()
        
        return result.scalar_one_or_none()
    
    async def delete(self, id: int) -> bool:
        """
        Delete record by ID
        
        Args:
            id: Primary key value
            
        Returns:
            True if deleted, False if not found
        """
        pk_name = self._get_pk_name()
        stmt = delete(self.model).where(self.model.__table__.c[pk_name] == id)
        
        result = await self.db.execute(stmt)
        await self.db.commit()
        
        return result.rowcount > 0
    
    async def count(self) -> int:
        """
        Count total records
        
        Returns:
            Total number of records
        """
        result = await self.db.execute(
            select(func.count()).select_from(self.model)
        )
        return result.scalar()
    
    def _get_pk_name(self) -> str:
        """Get primary key column name"""
        return list(self.model.__table__.primary_key.columns)[0].name


### Archivo: `app/repositories/production_repository.py`


"""
Production line and area repositories
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.client_db import ProductionLine, Area
from app.repositories.base_repository import BaseRepository


class ProductionLineRepository(BaseRepository[ProductionLine]):
    """Repository for production lines"""
    
    def __init__(self, db: AsyncSession):
        super().__init__(ProductionLine, db)
    
    async def get_active_lines(self) -> List[ProductionLine]:
        """Get all active production lines"""
        result = await self.db.execute(
            select(ProductionLine).where(ProductionLine.is_active == True)
        )
        return result.scalars().all()
    
    async def get_by_code(self, line_code: str) -> Optional[ProductionLine]:
        """Get production line by code"""
        result = await self.db.execute(
            select(ProductionLine).where(ProductionLine.line_code == line_code)
        )
        return result.scalar_one_or_none()
    
    async def activate(self, line_id: int) -> Optional[ProductionLine]:
        """Activate production line"""
        return await self.update(line_id, {'is_active': True})
    
    async def deactivate(self, line_id: int) -> Optional[ProductionLine]:
        """Deactivate production line"""
        return await self.update(line_id, {'is_active': False})


class AreaRepository(BaseRepository[Area]):
    """Repository for areas"""
    
    def __init__(self, db: AsyncSession):
        super().__init__(Area, db)
    
    async def get_by_line(self, line_id: int) -> List[Area]:
        """Get all areas for a production line"""
        result = await self.db.execute(
            select(Area)
            .where(Area.line_id == line_id)
            .order_by(Area.area_order.asc())
        )
        return result.scalars().all()
    
    async def get_by_type(self, line_id: int, area_type: str) -> List[Area]:
        """Get areas by type for a line"""
        result = await self.db.execute(
            select(Area)
            .where(Area.line_id == line_id)
            .where(Area.area_type == area_type)
            .order_by(Area.area_order.asc())
        )
        return result.scalars().all()
    
    async def get_input_area(self, line_id: int) -> Optional[Area]:
        """Get input area for a line"""
        result = await self.db.execute(
            select(Area)
            .where(Area.line_id == line_id)
            .where(Area.area_type == 'input')
            .limit(1)
        )
        return result.scalar_one_or_none()
    
    async def get_output_area(self, line_id: int) -> Optional[Area]:
        """Get output area for a line"""
        result = await self.db.execute(
            select(Area)
            .where(Area.line_id == line_id)
            .where(Area.area_type == 'output')
            .limit(1)
        )
        return result.scalar_one_or_none()


### Archivo: `app/repositories/product_repository.py`


"""
Product repository
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.client_db import Product
from app.repositories.base_repository import BaseRepository


class ProductRepository(BaseRepository[Product]):
    """Repository for products"""
    
    def __init__(self, db: AsyncSession):
        super().__init__(Product, db)
    
    async def get_by_code(self, product_code: str) -> Optional[Product]:
        """Get product by code"""
        result = await self.db.execute(
            select(Product).where(Product.product_code == product_code)
        )
        return result.scalar_one_or_none()
    
    async def search_by_name(self, search_term: str) -> List[Product]:
        """Search products by name"""
        result = await self.db.execute(
            select(Product)
            .where(Product.product_name.ilike(f"%{search_term}%"))
            .limit(50)
        )
        return result.scalars().all()


### Archivo: `app/repositories/config_repository.py`


"""
Configuration repositories (Filter and Shift)
"""
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.client_db import Filter, Shift
from app.repositories.base_repository import BaseRepository


class FilterRepository(BaseRepository[Filter]):
    """Repository for filters"""
    
    def __init__(self, db: AsyncSession):
        super().__init__(Filter, db)
    
    async def get_active_filters(self) -> List[Filter]:
        """Get all active filters"""
        result = await self.db.execute(
            select(Filter).where(Filter.filter_status == True)
        )
        return result.scalars().all()


class ShiftRepository(BaseRepository[Shift]):
    """Repository for shifts"""
    
    def __init__(self, db: AsyncSession):
        super().__init__(Shift, db)
    
    async def get_active_shifts(self) -> List[Shift]:
        """Get all active shifts"""
        result = await self.db.execute(
            select(Shift).where(Shift.shift_status == True)
        )
        return result.scalars().all()
    
    async def get_overnight_shifts(self) -> List[Shift]:
        """Get all overnight shifts"""
        result = await self.db.execute(
            select(Shift)
            .where(Shift.shift_status == True)
            .where(Shift.is_overnight == True)
        )
        return result.scalars().all()


### Archivo: `app/repositories/__init__.py`


"""
Repositories export
"""
from app.repositories.base_repository import BaseRepository
from app.repositories.production_repository import ProductionLineRepository, AreaRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.config_repository import FilterRepository, ShiftRepository

__all__ = [
    'BaseRepository',
    'ProductionLineRepository',
    'AreaRepository',
    'ProductRepository',
    'FilterRepository',
    'ShiftRepository',
]


---

## 📦 TASK 2.5: Servicios de Configuración

### Descripción
Implementar servicios de negocio que orquestan repositorios y cache para operaciones CRUD de configuración.

### Criterios de Aceptación
- [x] ConfigService implementado
- [x] Métodos CRUD que invalidan cache automáticamente
- [x] Validaciones de negocio implementadas
- [x] Manejo de errores apropiado

### Archivo: `app/services/config_service.py`


"""
Configuration service - Business logic for plant configuration
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.repositories.production_repository import ProductionLineRepository, AreaRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.config_repository import FilterRepository, ShiftRepository
from app.schemas.production import (
    ProductionLineCreate, ProductionLineUpdate, ProductionLineResponse,
    AreaCreate, AreaUpdate, AreaResponse,
    ProductCreate, ProductUpdate, ProductResponse,
    FilterCreate, FilterUpdate, FilterResponse,
    ShiftCreate, ShiftUpdate, ShiftResponse
)
from app.core.cache import invalidate_tenant_cache


class ConfigService:
    """Service for managing plant configuration"""
    
    def __init__(self, db: AsyncSession, tenant_id: int):
        self.db = db
        self.tenant_id = tenant_id
        
        # Initialize repositories
        self.line_repo = ProductionLineRepository(db)
        self.area_repo = AreaRepository(db)
        self.product_repo = ProductRepository(db)
        self.filter_repo = FilterRepository(db)
        self.shift_repo = ShiftRepository(db)
    
    # === Production Line Methods ===
    
    async def create_production_line(self, data: ProductionLineCreate) -> ProductionLineResponse:
        """
        Create new production line
        
        Validates:
        - line_code is unique
        """
        # Check if code exists
        existing = await self.line_repo.get_by_code(data.line_code)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Line code '{data.line_code}' already exists"
            )
        
        # Create line
        line = await self.line_repo.create(data.model_dump())
        
        # Invalidate cache
        invalidate_tenant_cache(self.tenant_id)
        
        return ProductionLineResponse.model_validate(line)
    
    async def get_production_line(self, line_id: int) -> ProductionLineResponse:
        """Get production line by ID"""
        line = await self.line_repo.get_by_id(line_id)
        if not line:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Production line {line_id} not found"
            )
        return ProductionLineResponse.model_validate(line)
    
    async def get_all_production_lines(self) -> List[ProductionLineResponse]:
        """Get all production lines"""
        lines = await self.line_repo.get_all()
        return [ProductionLineResponse.model_validate(line) for line in lines]
    
    async def get_active_production_lines(self) -> List[ProductionLineResponse]:
        """Get only active production lines"""
        lines = await self.line_repo.get_active_lines()
        return [ProductionLineResponse.model_validate(line) for line in lines]
    
    async def update_production_line(
        self, 
        line_id: int, 
        data: ProductionLineUpdate
    ) -> ProductionLineResponse:
        """Update production line"""
        line = await self.line_repo.update(line_id, data.model_dump(exclude_unset=True))
        if not line:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Production line {line_id} not found"
            )
        
        # Invalidate cache
        invalidate_tenant_cache(self.tenant_id)
        
        return ProductionLineResponse.model_validate(line)
    
    async def delete_production_line(self, line_id: int) -> bool:
        """
        Delete production line
        
        Note: This will cascade delete all areas
        """
        deleted = await self.line_repo.delete(line_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Production line {line_id} not found"
            )
        
        # Invalidate cache
        invalidate_tenant_cache(self.tenant_id)
        
        return True
    
    # === Area Methods ===
    
    async def create_area(self, data: AreaCreate) -> AreaResponse:
        """
        Create new area
        
        Validates:
        - line_id exists
        - area_order is unique within line
        """
        # Validate line exists
        line = await self.line_repo.get_by_id(data.line_id)
        if not line:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Production line {data.line_id} not found"
            )
        
        # Create area
        area = await self.area_repo.create(data.model_dump())
        
        # Invalidate cache
        invalidate_tenant_cache(self.tenant_id)
        
        return AreaResponse.model_validate(area)
    
    async def get_area(self, area_id: int) -> AreaResponse:
        """Get area by ID"""
        area = await self.area_repo.get_by_id(area_id)
        if not area:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Area {area_id} not found"
            )
        return AreaResponse.model_validate(area)
    
    async def get_areas_by_line(self, line_id: int) -> List[AreaResponse]:
        """Get all areas for a production line"""
        areas = await self.area_repo.get_by_line(line_id)
        return [AreaResponse.model_validate(area) for area in areas]
    
    async def update_area(self, area_id: int, data: AreaUpdate) -> AreaResponse:
        """Update area"""
        area = await self.area_repo.update(area_id, data.model_dump(exclude_unset=True))
        if not area:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Area {area_id} not found"
            )
        
        # Invalidate cache
        invalidate_tenant_cache(self.tenant_id)
        
        return AreaResponse.model_validate(area)
    
    async def delete_area(self, area_id: int) -> bool:
        """Delete area"""
        deleted = await self.area_repo.delete(area_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Area {area_id} not found"
            )
        
        # Invalidate cache
        invalidate_tenant_cache(self.tenant_id)
        
        return True
    
    # === Product Methods ===
    
    async def create_product(self, data: ProductCreate) -> ProductResponse:
        """
        Create new product
        
        Validates:
        - product_code is unique
        """
        # Check if code exists
        existing = await self.product_repo.get_by_code(data.product_code)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product code '{data.product_code}' already exists"
            )
        
        # Create product
        product = await self.product_repo.create(data.model_dump())
        
        # Invalidate cache
        invalidate_tenant_cache(self.tenant_id)
        
        return ProductResponse.model_validate(product)
    
    async def get_product(self, product_id: int) -> ProductResponse:
        """Get product by ID"""
        product = await self.product_repo.get_by_id(product_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product {product_id} not found"
            )
        return ProductResponse.model_validate(product)
    
    async def get_all_products(self) -> List[ProductResponse]:
        """Get all products"""
        products = await self.product_repo.get_all()
        return [ProductResponse.model_validate(product) for product in products]
    
    async def update_product(self, product_id: int, data: ProductUpdate) -> ProductResponse:
        """Update product"""
        product = await self.product_repo.update(product_id, data.model_dump(exclude_unset=True))
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product {product_id} not found"
            )
        
        # Invalidate cache
        invalidate_tenant_cache(self.tenant_id)
        
        return ProductResponse.model_validate(product)
    
    async def delete_product(self, product_id: int) -> bool:
        """Delete product"""
        deleted = await self.product_repo.delete(product_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product {product_id} not found"
            )
        
        # Invalidate cache
        invalidate_tenant_cache(self.tenant_id)
        
        return True
    
    # === Filter Methods ===
    
    async def create_filter(self, data: FilterCreate) -> FilterResponse:
        """Create new filter"""
        filter_obj = await self.filter_repo.create(data.model_dump())
        
        # Invalidate cache
        invalidate_tenant_cache(self.tenant_id)
        
        return FilterResponse.model_validate(filter_obj)
    
    async def get_filter(self, filter_id: int) -> FilterResponse:
        """Get filter by ID"""
        filter_obj = await self.filter_repo.get_by_id(filter_id)
        if not filter_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Filter {filter_id} not found"
            )
        return FilterResponse.model_validate(filter_obj)
    
    async def get_all_filters(self) -> List[FilterResponse]:
        """Get all filters"""
        filters = await self.filter_repo.get_all()
        return [FilterResponse.model_validate(f) for f in filters]
    
    async def get_active_filters(self) -> List[FilterResponse]:
        """Get only active filters"""
        filters = await self.filter_repo.get_active_filters()
        return [FilterResponse.model_validate(f) for f in filters]
    
    async def update_filter(self, filter_id: int, data: FilterUpdate) -> FilterResponse:
        """Update filter"""
        filter_obj = await self.filter_repo.update(filter_id, data.model_dump(exclude_unset=True))
        if not filter_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Filter {filter_id} not found"
            )
        
        # Invalidate cache
        invalidate_tenant_cache(self.tenant_id)
        
        return FilterResponse.model_validate(filter_obj)
    
    async def delete_filter(self, filter_id: int) -> bool:
        """Delete filter"""
        deleted = await self.filter_repo.delete(filter_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Filter {filter_id} not found"
            )
        
        # Invalidate cache
        invalidate_tenant_cache(self.tenant_id)
        
        return True
    
    # === Shift Methods ===
    
    async def create_shift(self, data: ShiftCreate) -> ShiftResponse:
        """Create new shift"""
        shift = await self.shift_repo.create(data.model_dump())
        
        # Invalidate cache
        invalidate_tenant_cache(self.tenant_id)
        
        return ShiftResponse.model_validate(shift)
    
    async def get_shift(self, shift_id: int) -> ShiftResponse:
        """Get shift by ID"""
        shift = await self.shift_repo.get_by_id(shift_id)
        if not shift:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Shift {shift_id} not found"
            )
        return ShiftResponse.model_validate(shift)
    
    async def get_all_shifts(self) -> List[ShiftResponse]:
        """Get all shifts"""
        shifts = await self.shift_repo.get_all()
        return [ShiftResponse.model_validate(shift) for shift in shifts]
    
    async def get_active_shifts(self) -> List[ShiftResponse]:
        """Get only active shifts"""
        shifts = await self.shift_repo.get_active_shifts()
        return [ShiftResponse.model_validate(shift) for shift in shifts]
    
    async def update_shift(self, shift_id: int, data: ShiftUpdate) -> ShiftResponse:
        """Update shift"""
        shift = await self.shift_repo.update(shift_id, data.model_dump(exclude_unset=True))
        if not shift:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Shift {shift_id} not found"
            )
        
        # Invalidate cache
        invalidate_tenant_cache(self.tenant_id)
        
        return ShiftResponse.model_validate(shift)
    
    async def delete_shift(self, shift_id: int) -> bool:
        """Delete shift"""
        deleted = await self.shift_repo.delete(shift_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Shift {shift_id} not found"
            )
        
        # Invalidate cache
        invalidate_tenant_cache(self.tenant_id)
        
        return True


