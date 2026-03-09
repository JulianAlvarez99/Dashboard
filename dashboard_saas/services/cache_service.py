"""
CacheService — Orchestrates loading metadata into MetadataCache.

Connects the repository (SQL queries) with the cache (in-memory store).
Sync-only: uses DatabaseManager's sync sessions.
"""

import logging
import time

from dashboard_saas.core.cache import metadata_cache
from dashboard_saas.core.database import db_manager
from dashboard_saas.repositories.metadata_repository import MetadataRepository

logger = logging.getLogger(__name__)


class CacheService:
    """
    Orchestrates the cache loading process.

    Usage:
        CacheService.load_for_tenant("cliente_centralnorte")
    """

    @staticmethod
    def load_for_tenant(db_name: str) -> dict:
        """
        Load all reference data for a tenant into the cache.

        If the cache is already loaded for this tenant, this is a no-op.
        Returns a summary of what was loaded.

        Args:
            db_name: Tenant database name.

        Returns:
            dict with status, tenant, and row counts.
        """
        # Skip if already loaded for this tenant
        if metadata_cache.current_tenant == db_name and metadata_cache.is_loaded:
            logger.info("Cache already loaded for %s — skipping", db_name)
            return {
                "status": "already_loaded",
                "tenant": db_name,
                "info": metadata_cache.get_cache_info(),
            }

        logger.info("Loading cache for tenant: %s", db_name)
        start = time.time()

        # Clear stale data
        metadata_cache.clear()

        # ── Load tenant metadata ────────────────────────────────
        with db_manager.get_tenant_session(db_name) as session:
            metadata_cache.store("production_lines", MetadataRepository.fetch_production_lines(session))
            metadata_cache.store("areas", MetadataRepository.fetch_areas(session))
            metadata_cache.store("products", MetadataRepository.fetch_products(session))
            metadata_cache.store("shifts", MetadataRepository.fetch_shifts(session))
            metadata_cache.store("filters", MetadataRepository.fetch_filters(session))
            metadata_cache.store("failures", MetadataRepository.fetch_failures(session))
            metadata_cache.store("incidents", MetadataRepository.fetch_incidents(session))

        # ── Load global metadata ────────────────────────────────
        with db_manager.get_global_session() as session:
            metadata_cache.store("widget_catalog", MetadataRepository.fetch_widget_catalog(session))

        # Mark tenant as loaded
        metadata_cache.set_tenant(db_name)

        # ── Synchronize structural engines ──────────────────────
        try:
            from dashboard_saas.services.filters.engine import filter_engine
            from dashboard_saas.services.widgets.engine import widget_engine
            filter_engine.load_filters()
            widget_engine.load_widgets()
            logger.info("Filter and Widget engines synced with new cache.")
        except Exception as e:
            logger.error("Failed to sync structural engines with cache: %s", e)

        elapsed = round(time.time() - start, 3)
        logger.info("Cache loaded for %s in %.3fs", db_name, elapsed)

        return {
            "status": "loaded",
            "tenant": db_name,
            "elapsed_seconds": elapsed,
            "info": metadata_cache.get_cache_info(),
        }

    @staticmethod
    def refresh(db_name: str = None) -> dict:
        """Force-reload cache for the given (or current) tenant."""
        target = db_name or metadata_cache.current_tenant
        if not target:
            raise RuntimeError("Cannot refresh: no tenant loaded yet")

        # Clear and reload
        metadata_cache.clear()
        return CacheService.load_for_tenant(target)
