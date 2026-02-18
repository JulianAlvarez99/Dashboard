"""
HTTPClient — Async HTTP wrapper with auth resolution.

Single Responsibility: execute a single HTTP request given an
``APIEndpoint`` config.  No YAML loading, no caching, no routing.

Handles:
  - Auth injection (bearer, api_key, basic) from environment variables.
  - Timeout enforcement per endpoint.
  - Response-key extraction (dot-notation path into JSON response).
  - Structured error handling — never raises; returns error dicts.

Usage::

    from new_app.services.broker.http_client import http_client

    result = await http_client.fetch(endpoint, extra_params={"date": "2026-01-15"})
    # result = {"ok": True, "data": {...}, "status": 200}
    # or      {"ok": False, "error": "Connection timeout", "status": 0}
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import httpx

from new_app.services.broker.api_config import APIEndpoint

logger = logging.getLogger(__name__)

# Reusable result type
APIResult = Dict[str, Any]


class HTTPClient:
    """
    Executes async HTTP requests based on ``APIEndpoint`` definitions.

    Stateless — each call creates and destroys its own ``httpx.AsyncClient``
    to stay compatible with cPanel's limited connection environment.
    """

    async def fetch(
        self,
        endpoint: APIEndpoint,
        extra_params: Optional[Dict[str, Any]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        extra_body: Optional[Dict[str, Any]] = None,
    ) -> APIResult:
        """
        Execute a single HTTP request for the given endpoint.

        Args:
            endpoint:      Parsed APIEndpoint from YAML config.
            extra_params:  Additional query params to merge.
            extra_headers: Additional headers to merge.
            extra_body:    Additional body fields to merge (POST only).

        Returns:
            ``{"ok": True, "data": ..., "status": int, "api_id": str}``
            or ``{"ok": False, "error": str, "status": int, "api_id": str}``
        """
        headers = self._build_headers(endpoint, extra_headers)
        params = {**endpoint.params, **(extra_params or {})}
        body = {**endpoint.body, **(extra_body or {})} if endpoint.method == "POST" else None

        try:
            async with httpx.AsyncClient(timeout=endpoint.timeout) as client:
                response = await self._send_request(
                    client, endpoint, headers, params, body,
                )

            if response.status_code >= 400:
                return self._error_result(
                    endpoint.api_id,
                    f"HTTP {response.status_code}: {response.text[:200]}",
                    response.status_code,
                )

            data = response.json()
            extracted = self._extract_response_key(data, endpoint.response_key)

            return {
                "ok": True,
                "data": extracted,
                "status": response.status_code,
                "api_id": endpoint.api_id,
            }

        except httpx.TimeoutException:
            return self._error_result(
                endpoint.api_id,
                f"Timeout after {endpoint.timeout}s",
                0,
            )
        except httpx.ConnectError as exc:
            return self._error_result(
                endpoint.api_id,
                f"Connection failed: {exc}",
                0,
            )
        except Exception as exc:
            return self._error_result(
                endpoint.api_id,
                f"Unexpected error: {exc}",
                0,
            )

    # ─────────────────────────────────────────────────────────
    #  INTERNAL HELPERS
    # ─────────────────────────────────────────────────────────

    def _build_headers(
        self,
        endpoint: APIEndpoint,
        extra: Optional[Dict[str, str]],
    ) -> Dict[str, str]:
        """
        Merge endpoint headers + extra headers + auth header.
        """
        headers = {**endpoint.headers, **(extra or {})}
        auth_header = self._resolve_auth(endpoint)
        if auth_header:
            headers.update(auth_header)
        return headers

    @staticmethod
    def _resolve_auth(endpoint: APIEndpoint) -> Optional[Dict[str, str]]:
        """
        Read the auth token from environment and return the header.

        Supports: bearer, api_key, basic, none.
        """
        if endpoint.auth_type == "none" or not endpoint.auth_env_var:
            return None

        token = os.environ.get(endpoint.auth_env_var, "")
        if not token:
            logger.warning(
                f"[HTTPClient] Env var '{endpoint.auth_env_var}' is empty "
                f"for api_id='{endpoint.api_id}'"
            )
            return None

        if endpoint.auth_type == "bearer":
            return {"Authorization": f"Bearer {token}"}
        if endpoint.auth_type == "api_key":
            return {"X-API-Key": token}
        if endpoint.auth_type == "basic":
            import base64
            encoded = base64.b64encode(token.encode()).decode()
            return {"Authorization": f"Basic {encoded}"}

        return None

    @staticmethod
    async def _send_request(
        client: httpx.AsyncClient,
        endpoint: APIEndpoint,
        headers: Dict[str, str],
        params: Dict[str, Any],
        body: Optional[Dict[str, Any]],
    ) -> httpx.Response:
        """Dispatch GET or POST based on endpoint config."""
        if endpoint.method == "POST":
            return await client.post(
                endpoint.base_url,
                headers=headers,
                params=params,
                json=body,
            )
        return await client.get(
            endpoint.base_url,
            headers=headers,
            params=params,
        )

    @staticmethod
    def _extract_response_key(data: Any, response_key: Optional[str]) -> Any:
        """
        Navigate a dot-notation path into the response JSON.

        ``"data.orders"`` → ``data["data"]["orders"]``
        Returns the full response if no response_key is set.
        """
        if not response_key:
            return data

        for key in response_key.split("."):
            if isinstance(data, dict):
                data = data.get(key)
            else:
                return None

        return data

    @staticmethod
    def _error_result(api_id: str, error: str, status: int) -> APIResult:
        """Build a standardized error result dict."""
        logger.error(f"[HTTPClient] {api_id}: {error}")
        return {
            "ok": False,
            "error": error,
            "status": status,
            "api_id": api_id,
            "data": None,
        }


# ── Singleton ────────────────────────────────────────────────────
http_client = HTTPClient()
