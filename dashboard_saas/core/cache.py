"""
MetadataCache — Thread-safe in-memory cache for reference data.

Simplified rewrite: sync-only, single-tenant per process.
Loaded on startup using DEFAULT_DB_NAME from .env.

Cached entities (from tenant DB):
  production_lines, areas, products, shifts, filters, failures, incidents.
Cached entities (from global DB):
  widget_catalog.
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


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
    Singleton in-memory cache — single-tenant per process.

    Thread-safe via threading.Lock (sync callers only).
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
            self._lock = threading.Lock()
            self._current_tenant: Optional[str] = None
            MetadataCache._initialized = True

    # ─────────────────────────────────────────────────────────────
    #  STATUS
    # ─────────────────────────────────────────────────────────────

    @property
    def is_loaded(self) -> bool:
        return len(self._cache) > 0

    @property
    def current_tenant(self) -> Optional[str]:
        """The tenant db_name whose data is currently cached."""
        return self._current_tenant

    # ─────────────────────────────────────────────────────────────
    #  STORE (called by cache_service)
    # ─────────────────────────────────────────────────────────────

    def store(self, key: str, data: Any) -> None:
        """Store a dataset in the cache."""
        self._cache[key] = CacheEntry(data=data)

    def set_tenant(self, db_name: str) -> None:
        """Mark which tenant is loaded."""
        self._current_tenant = db_name

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

    # Widget catalog (global DB)
    def get_widget_catalog(self) -> Dict[int, dict]:
        return self._get("widget_catalog")

    def get_widget(self, widget_id: int) -> Optional[dict]:
        return self.get_widget_catalog().get(widget_id)

    # ─────────────────────────────────────────────────────────────
    #  MANAGEMENT
    # ─────────────────────────────────────────────────────────────

    def clear(self) -> None:
        """Wipe the entire cache."""
        with self._lock:
            self._cache.clear()
            self._current_tenant = None
            logger.info("Cache cleared")

    def get_cache_info(self) -> Dict[str, Any]:
        """Return a summary for the /system/cache/status endpoint."""
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
            "is_loaded": self.is_loaded,
            "tables": tables,
        }


# ── Global singleton ─────────────────────────────────────────────
metadata_cache = MetadataCache()
