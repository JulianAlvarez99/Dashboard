"""
JWT utilities — token creation and validation.

Single Responsibility: wrap PyJWT so the rest of the codebase never
imports ``jwt`` directly.  All JWT policy (algorithm, expiry, claims)
lives here.

Usage::

    from new_app.core.jwt_utils import create_access_token, decode_access_token

    token  = create_access_token(user_id=1, username="ops", role="ADMIN",
                                  db_name="client_acme", tenant_id=5)
    claims = decode_access_token(token)   # raises jwt.InvalidTokenError on failure
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import jwt

from new_app.core.config import get_settings

logger = logging.getLogger(__name__)


def create_access_token(
    user_id: int,
    username: str,
    role: str,
    db_name: str,
    tenant_id: int,
) -> str:
    """
    Issue a signed JWT access token for a successfully authenticated user.

    Claims:
      sub        → str(user_id)
      username   → str
      role       → "ADMIN" | "MANAGER" | "OPERATOR"
      db_name    → tenant database name (needed by FastAPI to scope queries)
      tenant_id  → int
      type       → "access"
      iat / exp  → issued-at / expiry timestamps

    Args:
        user_id:   Primary-key of the user in ``camet_global.users``.
        username:  Login name (for logging/audit).
        role:      User role string.
        db_name:   Resolved tenant database name (e.g. ``client_acme_db``).
        tenant_id: Tenant FK from ``camet_global``.

    Returns:
        Signed JWT string.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "db_name": db_name,
        "tenant_id": tenant_id,
        "type": "access",
        "iat": now,
        "exp": expire,
    }

    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Validate and decode a JWT access token.

    Verifies:
      - Signature (using ``JWT_SECRET_KEY``).
      - Expiry (``exp`` claim).
      - Token type must be ``"access"``.

    Args:
        token: Raw JWT string (without ``Bearer `` prefix).

    Returns:
        Decoded claims dict.

    Raises:
        jwt.ExpiredSignatureError: Token has expired.
        jwt.InvalidTokenError:     Signature invalid, malformed, wrong type, etc.
    """
    settings = get_settings()
    payload: Dict[str, Any] = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Not an access token")
    return payload
