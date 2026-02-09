"""
MetadataCache - In-memory cache for reference data
Stores PRODUCT, AREA, PRODUCTION_LINE, SHIFT for application-side joins
Avoids heavy database JOINs by enriching data in Python with Pandas
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import db_manager


@dataclass
class CacheEntry:
    """Individual cache entry with metadata"""
    data: Any
    loaded_at: datetime = field(default_factory=datetime.now)
    
    @property
    def age_seconds(self) -> float:
        """Seconds since this entry was loaded"""
        return (datetime.now() - self.loaded_at).total_seconds()


class MetadataCache:
    """
    Singleton cache for reference/metadata tables.
    Loaded once at startup, can be refreshed manually.
    
    Cached tables (from tenant DB):
    - PRODUCTION_LINE: line_id -> {line_name, line_code, downtime_threshold, ...}
    - AREA: area_id -> {area_name, area_type, line_id, ...}
    - PRODUCT: product_id -> {product_name, product_code, product_weight, ...}
    - SHIFT: shift_id -> {shift_name, start_time, end_time, ...}
    - FILTER: filter_id -> {filter_name, description, additional_filter, ...}
    - FAILURE: failure_id -> {type_failure, description}
    - INCIDENT: incident_id -> {failure_id, incident_code, description, has_solution}
    
    Cached tables (from global DB):
    - WIDGET_CATALOG: widget_id -> {widget_name, description}
    """
    
    _instance: Optional["MetadataCache"] = None
    _initialized: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._cache: Dict[str, CacheEntry] = {}
            self._lock = asyncio.Lock()
            MetadataCache._initialized = True
    
    @property
    def is_loaded(self) -> bool:
        """Check if cache has been populated"""
        return len(self._cache) > 0
    
    async def load_all(self) -> None:
        """Load all metadata tables into cache"""
        async with self._lock:
            await self._load_tenant_metadata()
            await self._load_global_metadata()
    
    async def _load_tenant_metadata(self) -> None:
        """Load metadata from tenant database"""
        async with db_manager.get_tenant_session() as session:
            # Production Lines
            result = await session.execute(text("""
                SELECT line_id, line_name, line_code, is_active, 
                       availability, performance, downtime_threshold,
                       auto_detect_downtime
                FROM production_line
                WHERE is_active = 1
            """))
            rows = result.mappings().all()
            self._cache["production_lines"] = CacheEntry(
                data={row["line_id"]: dict(row) for row in rows}
            )
            
            # Areas
            result = await session.execute(text("""
                SELECT area_id, line_id, area_name, area_type, area_order,
                       coord_x1, coord_y1, coord_x2, coord_y2
                FROM area
            """))
            rows = result.mappings().all()
            self._cache["areas"] = CacheEntry(
                data={row["area_id"]: dict(row) for row in rows}
            )
            
            # Products
            result = await session.execute(text("""
                SELECT product_id, product_name, product_code, 
                       product_weight, product_color, production_std, product_per_batch
                FROM product
            """))
            rows = result.mappings().all()
            self._cache["products"] = CacheEntry(
                data={row["product_id"]: dict(row) for row in rows}
            )
            
            # Shifts
            result = await session.execute(text("""
                SELECT shift_id, shift_name, description, shift_status,
                       days_implemented, start_time, end_time, is_overnight
                FROM shift
                WHERE shift_status = 1
            """))
            rows = result.mappings().all()
            self._cache["shifts"] = CacheEntry(
                data={row["shift_id"]: dict(row) for row in rows}
            )
            
            # Filters
            result = await session.execute(text("""
                SELECT filter_id, filter_name, description, filter_status,
                       display_order, additional_filter
                FROM filter
                WHERE filter_status = 1
                ORDER BY display_order
            """))
            rows = result.mappings().all()
            self._cache["filters"] = CacheEntry(
                data={row["filter_id"]: dict(row) for row in rows}
            )
            
            # Failures
            result = await session.execute(text("""
                SELECT failure_id, type_failure, description
                FROM failure
            """))
            rows = result.mappings().all()
            self._cache["failures"] = CacheEntry(
                data={row["failure_id"]: dict(row) for row in rows}
            )
            
            # Incidents
            result = await session.execute(text("""
                SELECT incident_id, failure_id, incident_code,
                       description, has_solution, solution
                FROM incident
            """))
            rows = result.mappings().all()
            self._cache["incidents"] = CacheEntry(
                data={row["incident_id"]: dict(row) for row in rows}
            )
    
    async def _load_global_metadata(self) -> None:
        """Load metadata from global database"""
        async with db_manager.get_global_session() as session:
            # Widget Catalog
            result = await session.execute(text("""
                SELECT widget_id, widget_name, description
                FROM widget_catalog
            """))
            rows = result.mappings().all()
            self._cache["widget_catalog"] = CacheEntry(
                data={row["widget_id"]: dict(row) for row in rows}
            )
    
    # --- Getters for cached data ---
    
    def get_production_lines(self) -> Dict[int, dict]:
        """Get all production lines indexed by line_id"""
        entry = self._cache.get("production_lines")
        return entry.data if entry else {}
    
    def get_production_line(self, line_id: int) -> Optional[dict]:
        """Get single production line by ID"""
        return self.get_production_lines().get(line_id)
    
    def get_areas(self) -> Dict[int, dict]:
        """Get all areas indexed by area_id"""
        entry = self._cache.get("areas")
        return entry.data if entry else {}
    
    def get_area(self, area_id: int) -> Optional[dict]:
        """Get single area by ID"""
        return self.get_areas().get(area_id)
    
    def get_areas_by_line(self, line_id: int) -> List[dict]:
        """Get all areas for a specific production line"""
        return [
            area for area in self.get_areas().values()
            if area["line_id"] == line_id
        ]
    
    def get_products(self) -> Dict[int, dict]:
        """Get all products indexed by product_id"""
        entry = self._cache.get("products")
        return entry.data if entry else {}
    
    def get_product(self, product_id: int) -> Optional[dict]:
        """Get single product by ID"""
        return self.get_products().get(product_id)
    
    def get_shifts(self) -> Dict[int, dict]:
        """Get all shifts indexed by shift_id"""
        entry = self._cache.get("shifts")
        return entry.data if entry else {}
    
    def get_shift(self, shift_id: int) -> Optional[dict]:
        """Get single shift by ID"""
        return self.get_shifts().get(shift_id)
    
    def get_filters(self) -> Dict[int, dict]:
        """Get all filters indexed by filter_id"""
        entry = self._cache.get("filters")
        return entry.data if entry else {}
    
    def get_filter(self, filter_id: int) -> Optional[dict]:
        """Get single filter by ID"""
        return self.get_filters().get(filter_id)
    
    def get_failures(self) -> Dict[int, dict]:
        """Get all failures indexed by failure_id"""
        entry = self._cache.get("failures")
        return entry.data if entry else {}
    
    def get_failure(self, failure_id: int) -> Optional[dict]:
        """Get single failure by ID"""
        return self.get_failures().get(failure_id)
    
    def get_incidents(self) -> Dict[int, dict]:
        """Get all incidents indexed by incident_id"""
        entry = self._cache.get("incidents")
        return entry.data if entry else {}
    
    def get_incidents_by_failure(self, failure_id: int) -> List[dict]:
        """Get all incidents for a specific failure type"""
        return [
            inc for inc in self.get_incidents().values()
            if inc["failure_id"] == failure_id
        ]
    
    def get_widget_catalog(self) -> Dict[int, dict]:
        """Get all widgets indexed by widget_id"""
        entry = self._cache.get("widget_catalog")
        return entry.data if entry else {}
    
    def get_widget(self, widget_id: int) -> Optional[dict]:
        """Get single widget by ID"""
        return self.get_widget_catalog().get(widget_id)
    
    # --- Cache management ---
    
    async def refresh(self) -> None:
        """Force refresh of all cached data"""
        await self.load_all()
    
    def clear(self) -> None:
        """Clear all cached data"""
        self._cache.clear()
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            name: {
                "count": len(entry.data) if isinstance(entry.data, dict) else 1,
                "loaded_at": entry.loaded_at.isoformat(),
                "age_seconds": entry.age_seconds
            }
            for name, entry in self._cache.items()
        }


# Global cache instance
metadata_cache = MetadataCache()
