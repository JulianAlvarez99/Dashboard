"""
ExternalAPIService — Orchestrates config lookup + HTTP calls with TTL cache.

Single Responsibility: given an ``api_id``, load its config and execute
the request via HTTPClient.  Adds an optional in-memory TTL cache so
repeated calls within ``cache_ttl`` seconds return instantly.

Does NOT decide *when* to call — that's the DataBroker's job.

Usage::

    from new_app.services.broker.external_api_service import external_api_service

    result = await external_api_service.fetch("erp_production", extra_params={"date": "2026-01-15"})
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from new_app.services.broker.api_config import APIEndpoint, api_config_loader
from new_app.services.broker.http_client import APIResult, http_client

logger = logging.getLogger(__name__)


class _CacheEntry:
    """Internal TTL cache entry."""
    __slots__ = ("data", "expires_at")

    def __init__(self, data: Any, ttl: int):
        self.data = data
        self.expires_at = time.monotonic() + ttl


class ExternalAPIService:
    """
    High-level service for consuming external APIs.

    Responsibilities:
      1. Resolve ``api_id`` → ``APIEndpoint`` via APIConfigLoader.
      2. Delegate HTTP execution to HTTPClient.
      3. Cache successful responses for ``cache_ttl`` seconds.
    """

    def __init__(self) -> None:
        self._cache: Dict[str, _CacheEntry] = {}

    async def fetch(
        self,
        api_id: str,
        extra_params: Optional[Dict[str, Any]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        extra_body: Optional[Dict[str, Any]] = None,
        bypass_cache: bool = False,
    ) -> APIResult:
        """
        Fetch data from an external API by its ``api_id``.

        Args:
            api_id:        Key defined in ``external_apis.yml``.
            extra_params:  Additional query params to merge.
            extra_headers: Additional headers to merge.
            extra_body:    Additional body fields (POST only).
            bypass_cache:  If ``True``, skip the TTL cache.

        Returns:
            Same ``APIResult`` dict as ``HTTPClient.fetch()``.
        """
        endpoint = api_config_loader.get(api_id)
        if endpoint is None:
            return self._not_found(api_id)

        if not endpoint.enabled:
            return self._disabled(api_id)

        # Check TTL cache
        if not bypass_cache:
            cached = self._get_cached(api_id)
            if cached is not None:
                return cached

        result = await http_client.fetch(
            endpoint,
            extra_params=extra_params,
            extra_headers=extra_headers,
            extra_body=extra_body,
        )

        # Cache successful responses if TTL > 0
        if result["ok"] and endpoint.cache_ttl > 0:
            self._set_cached(api_id, result, endpoint.cache_ttl)

        return result

    async def fetch_many(
        self,
        api_ids: list[str],
        bypass_cache: bool = False,
    ) -> Dict[str, APIResult]:
        """
        Fetch multiple APIs concurrently.

        Returns a dict keyed by api_id.
        """
        import asyncio

        tasks = {
            api_id: self.fetch(api_id, bypass_cache=bypass_cache)
            for api_id in api_ids
        }
        results = await asyncio.gather(
            *tasks.values(), return_exceptions=True,
        )

        output: Dict[str, APIResult] = {}
        for api_id, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                output[api_id] = {
                    "ok": False,
                    "error": f"Unexpected: {result}",
                    "status": 0,
                    "api_id": api_id,
                    "data": None,
                }
            else:
                output[api_id] = result

        return output

    def clear_cache(self, api_id: Optional[str] = None) -> None:
        """
        Clear the TTL cache.

        Args:
            api_id: If given, clear only that key. Otherwise clear all.
        """
        if api_id:
            self._cache.pop(api_id, None)
        else:
            self._cache.clear()

    def list_available(self) -> list[dict]:
        """
        Return a summary of all configured (enabled) API endpoints.

        Useful for admin/diagnostic endpoints.
        """
        endpoints = api_config_loader.get_enabled()
        return [
            {
                "api_id": ep.api_id,
                "name": ep.name,
                "base_url": ep.base_url,
                "method": ep.method,
                "cache_ttl": ep.cache_ttl,
            }
            for ep in endpoints.values()
        ]

    # ─────────────────────────────────────────────────────────
    #  INTERNAL HELPERS
    # ─────────────────────────────────────────────────────────

    def _get_cached(self, api_id: str) -> Optional[APIResult]:
        """Return cached result if still valid, else None."""
        entry = self._cache.get(api_id)
        if entry is None:
            return None
        if time.monotonic() > entry.expires_at:
            del self._cache[api_id]
            return None
        logger.debug(f"[ExternalAPIService] Cache hit for '{api_id}'")
        return entry.data

    def _set_cached(self, api_id: str, result: APIResult, ttl: int) -> None:
        """Store a successful result in the TTL cache."""
        self._cache[api_id] = _CacheEntry(result, ttl)

    @staticmethod
    def _not_found(api_id: str) -> APIResult:
        """Return error for unknown api_id."""
        logger.warning(
            f"[ExternalAPIService] Unknown api_id='{api_id}'"
        )
        return {
            "ok": False,
            "error": f"API '{api_id}' not found in external_apis.yml",
            "status": 0,
            "api_id": api_id,
            "data": None,
        }

    @staticmethod
    def _disabled(api_id: str) -> APIResult:
        """Return error for disabled api_id."""
        logger.info(
            f"[ExternalAPIService] API '{api_id}' is disabled"
        )
        return {
            "ok": False,
            "error": f"API '{api_id}' is disabled",
            "status": 0,
            "api_id": api_id,
            "data": None,
        }


# ── Singleton ────────────────────────────────────────────────────
external_api_service = ExternalAPIService()
