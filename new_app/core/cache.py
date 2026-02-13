"""
MetadataCache — Thread-safe in-memory cache for reference data.

Loaded on-demand after user login (NOT at startup).
The cache is tenant-scoped: it stores data for the currently-active
tenant and tracks which tenant is loaded via ``current_tenant``.

Serves all application-side joins so that processors and services
never hit the database for static/reference data.

Cached entities:
  Tenant DB: production_lines, areas, products, shifts, filters,
             failures, incidents.
  Global DB: widget_catalog.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from new_app.core.database import db_manager


@dataclass
class CacheEntry:
    """Container for a cached dataset with load-time metadata."""
    data: Any
    loaded_at: datetime = field(default_factory=datetime.now)

    @property
    def age_seconds(self) -> float:
        return (datetime.now() - self.loaded_at).total_seconds()


class MetadataCache:
    """
    Singleton in-memory cache.

    Usage::

        from new_app.core.cache import metadata_cache

        lines = metadata_cache.get_production_lines()   # dict[int, dict]
        line  = metadata_cache.get_production_line(1)    # dict | None
    """

    _instance: Optional["MetadataCache"] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not MetadataCache._initialized:
            self._cache: Dict[str, CacheEntry] = {}
            self._lock = asyncio.Lock()
            self._current_tenant: Optional[str] = None
            MetadataCache._initialized = True

    # ─────────────────────────────────────────────────────────────
    #  LOAD
    # ─────────────────────────────────────────────────────────────

    @property
    def is_loaded(self) -> bool:
        return len(self._cache) > 0

    @property
    def current_tenant(self) -> Optional[str]:
        """The tenant db_name whose data is currently cached."""
        return self._current_tenant

    async def load_for_tenant(self, db_name: str) -> None:
        """
        Load (or reload) cache for a specific tenant.

        If the cache is already loaded for this tenant, this is a no-op.
        Use :meth:`refresh` to force a reload.

        Args:
            db_name: Tenant database name (e.g. ``cliente_centralnorte``).
        """
        if self._current_tenant == db_name and self.is_loaded:
            return  # already loaded for this tenant
        await self.load_all(db_name)

    async def load_all(self, db_name: Optional[str] = None) -> None:
        """
        Load every reference table into memory.

        Args:
            db_name: Tenant database name. If ``None`` the default
                     tenant DB from .env is used.
        """
        async with self._lock:
            self._cache.clear()  # wipe stale data from previous tenant
            self._current_tenant = db_name
            await self._load_tenant_metadata(db_name)
            await self._load_global_metadata()

    async def _load_tenant_metadata(self, db_name: Optional[str] = None) -> None:
        ctx = (
            db_manager.get_tenant_session_by_name(db_name)
            if db_name
            else db_manager.get_tenant_session()
        )
        async with ctx as session:
            await self._load_production_lines(session)
            await self._load_areas(session)
            await self._load_products(session)
            await self._load_shifts(session)
            await self._load_filters(session)
            await self._load_failures(session)
            await self._load_incidents(session)

    async def _load_global_metadata(self) -> None:
        async with db_manager.get_global_session() as session:
            await self._load_widget_catalog(session)

    # ── Individual loaders ───────────────────────────────────────

    async def _load_production_lines(self, session) -> None:
        result = await session.execute(text(
            "SELECT line_id, line_name, line_code, is_active, "
            "availability, performance, downtime_threshold, "
            "auto_detect_downtime "
            "FROM production_line WHERE is_active = 1"
        ))
        rows = result.mappings().all()
        self._cache["production_lines"] = CacheEntry(
            data={row["line_id"]: dict(row) for row in rows}
        )

    async def _load_areas(self, session) -> None:
        result = await session.execute(text(
            "SELECT area_id, line_id, area_name, area_type, area_order, "
            "coord_x1, coord_y1, coord_x2, coord_y2 FROM area"
        ))
        rows = result.mappings().all()
        self._cache["areas"] = CacheEntry(
            data={row["area_id"]: dict(row) for row in rows}
        )

    async def _load_products(self, session) -> None:
        result = await session.execute(text(
            "SELECT product_id, product_name, product_code, "
            "product_weight, product_color, production_std, product_per_batch "
            "FROM product"
        ))
        rows = result.mappings().all()
        self._cache["products"] = CacheEntry(
            data={row["product_id"]: dict(row) for row in rows}
        )

    async def _load_shifts(self, session) -> None:
        result = await session.execute(text(
            "SELECT shift_id, shift_name, description, shift_status, "
            "days_implemented, start_time, end_time, is_overnight "
            "FROM shift WHERE shift_status = 1"
        ))
        rows = result.mappings().all()
        self._cache["shifts"] = CacheEntry(
            data={row["shift_id"]: dict(row) for row in rows}
        )

    async def _load_filters(self, session) -> None:
        result = await session.execute(text(
            "SELECT filter_id, filter_name, description, filter_status, "
            "display_order, additional_filter "
            "FROM filter WHERE filter_status = 1 ORDER BY display_order"
        ))
        rows = result.mappings().all()
        self._cache["filters"] = CacheEntry(
            data={row["filter_id"]: dict(row) for row in rows}
        )

    async def _load_failures(self, session) -> None:
        result = await session.execute(text(
            "SELECT failure_id, type_failure, description FROM failure"
        ))
        rows = result.mappings().all()
        self._cache["failures"] = CacheEntry(
            data={row["failure_id"]: dict(row) for row in rows}
        )

    async def _load_incidents(self, session) -> None:
        result = await session.execute(text(
            "SELECT incident_id, failure_id, incident_code, "
            "description, has_solution, solution FROM incident"
        ))
        rows = result.mappings().all()
        self._cache["incidents"] = CacheEntry(
            data={row["incident_id"]: dict(row) for row in rows}
        )

    async def _load_widget_catalog(self, session) -> None:
        result = await session.execute(text(
            "SELECT widget_id, widget_name, description FROM widget_catalog"
        ))
        rows = result.mappings().all()
        self._cache["widget_catalog"] = CacheEntry(
            data={row["widget_id"]: dict(row) for row in rows}
        )

    # ─────────────────────────────────────────────────────────────
    #  GETTERS — typed accessors for cached data
    # ─────────────────────────────────────────────────────────────

    def _get(self, key: str) -> Dict:
        entry = self._cache.get(key)
        return entry.data if entry else {}

    # Production lines
    def get_production_lines(self) -> Dict[int, dict]:
        return self._get("production_lines")

    def get_production_line(self, line_id: int) -> Optional[dict]:
        return self.get_production_lines().get(line_id)

    def get_active_line_ids(self) -> List[int]:
        return list(self.get_production_lines().keys())

    # Areas
    def get_areas(self) -> Dict[int, dict]:
        return self._get("areas")

    def get_area(self, area_id: int) -> Optional[dict]:
        return self.get_areas().get(area_id)

    def get_areas_by_line(self, line_id: int) -> List[dict]:
        return [a for a in self.get_areas().values() if a["line_id"] == line_id]

    # Products
    def get_products(self) -> Dict[int, dict]:
        return self._get("products")

    def get_product(self, product_id: int) -> Optional[dict]:
        return self.get_products().get(product_id)

    # Shifts
    def get_shifts(self) -> Dict[int, dict]:
        return self._get("shifts")

    def get_shift(self, shift_id: int) -> Optional[dict]:
        return self.get_shifts().get(shift_id)

    # Filters
    def get_filters(self) -> Dict[int, dict]:
        return self._get("filters")

    def get_filter(self, filter_id: int) -> Optional[dict]:
        return self.get_filters().get(filter_id)

    # Failures
    def get_failures(self) -> Dict[int, dict]:
        return self._get("failures")

    def get_failure(self, failure_id: int) -> Optional[dict]:
        return self.get_failures().get(failure_id)

    # Incidents
    def get_incidents(self) -> Dict[int, dict]:
        return self._get("incidents")

    def get_incidents_by_failure(self, failure_id: int) -> List[dict]:
        return [
            i for i in self.get_incidents().values()
            if i["failure_id"] == failure_id
        ]

    # Widget catalog
    def get_widget_catalog(self) -> Dict[int, dict]:
        return self._get("widget_catalog")

    def get_widget(self, widget_id: int) -> Optional[dict]:
        return self.get_widget_catalog().get(widget_id)

    # ─────────────────────────────────────────────────────────────
    #  MANAGEMENT
    # ─────────────────────────────────────────────────────────────

    async def refresh(self, db_name: Optional[str] = None) -> None:
        """Force-reload everything for the given (or current) tenant."""
        target = db_name or self._current_tenant
        if not target:
            raise RuntimeError("Cannot refresh: no tenant loaded yet")
        self._current_tenant = None  # force reload
        await self.load_all(target)

    def clear(self) -> None:
        """Wipe the cache (used in tests or forced reset)."""
        self._cache.clear()
        self._current_tenant = None

    def get_cache_info(self) -> Dict[str, Any]:
        """Return a summary suitable for the /system/cache/info endpoint."""
        tables = {
            name: {
                "count": len(entry.data) if isinstance(entry.data, dict) else 1,
                "loaded_at": entry.loaded_at.isoformat(),
                "age_seconds": round(entry.age_seconds, 1),
            }
            for name, entry in self._cache.items()
        }
        return {
            "current_tenant": self._current_tenant,
            "tables": tables,
        }


# ── Global singleton ─────────────────────────────────────────────
metadata_cache = MetadataCache()
