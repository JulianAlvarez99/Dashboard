"""
FastAPI dependencies — Eliminates boilerplate in detection endpoints.

Single Responsibility: provide reusable FastAPI ``Depends()`` callables
for JWT validation, cache check, tenant resolution, and common request parsing.

Usage in endpoints::

    @router.post("/query")
    async def query_detections(
        ctx: TenantContext = Depends(require_tenant),
        req: DetectionQueryRequest = ...,
    ):
        # ctx.db_name, ctx.role, ctx.user_id are all available
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from new_app.core.cache import metadata_cache
from new_app.core.jwt_utils import decode_access_token
from new_app.services.data.line_resolver import line_resolver

logger = logging.getLogger(__name__)

# ── HTTP Bearer scheme (auto_error=False lets us return a 401 ourselves) ──
_bearer = HTTPBearer(auto_error=False)


@dataclass
class TenantContext:
    """Validated tenant context — guaranteed non-null db_name and JWT claims."""
    db_name: str
    user_id: int = 0
    username: str = ""
    role: str = "OPERATOR"
    tenant_id: int = 0


def require_cache() -> None:
    """Dependency: ensure MetadataCache is loaded (user has logged in)."""
    if not metadata_cache.is_loaded:
        raise HTTPException(
            status_code=503, detail="Cache not loaded — log in first"
        )


def require_tenant(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> TenantContext:
    """
    Dependency: validate JWT Bearer token and return the tenant context.

    Flow:
      1. Extract ``Authorization: Bearer <token>`` header.
      2. Validate and decode the JWT (signature + expiry).
      3. Extract ``db_name``, ``role``, ``user_id`` from claims.
      4. Verify the in-process MetadataCache is loaded for this session.

    Raises:
        401 — missing / expired / invalid token.
        503 — cache not loaded (user should log in again to reload cache).
    """
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authorization header missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token expired — please log in again",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as exc:
        logger.warning("[JWT] Invalid token: %s", exc)
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    db_name = payload.get("db_name", "")
    if not db_name:
        raise HTTPException(status_code=401, detail="Token missing db_name claim")

    # Verify the MetadataCache is warm for this session
    if not metadata_cache.is_loaded:
        raise HTTPException(
            status_code=503,
            detail="Cache not loaded — please log in again to reload session",
        )

    return TenantContext(
        db_name=db_name,
        user_id=int(payload.get("sub", 0)),
        username=payload.get("username", ""),
        role=payload.get("role", "OPERATOR"),
        tenant_id=int(payload.get("tenant_id", 0)),
    )


def resolve_line_ids_from_cleaned(cleaned: Dict[str, Any]) -> List[int]:
    """
    Resolve line IDs from a cleaned filter dict.

    Raises HTTP 400 if no lines can be resolved.
    """
    line_ids = line_resolver.resolve(cleaned)
    if not line_ids:
        raise HTTPException(
            status_code=400,
            detail="No production lines found for the given parameters",
        )
    return line_ids

