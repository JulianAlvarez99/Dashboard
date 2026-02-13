"""
Authentication utilities — Argon2 password hashing + user authentication.

Responsibilities:
- Hash / verify passwords with Argon2id.
- Authenticate a username+password combo against camet_global.
- Retrieve a user by ID (for session revalidation).
"""

from typing import Any, Dict, Optional

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.orm import Session

from new_app.core.config import settings
from new_app.models.global_models import Tenant, User


# ── Argon2 hasher (configured once) ─────────────────────────────

ph = PasswordHasher(
    time_cost=settings.ARGON2_TIME_COST,
    memory_cost=settings.ARGON2_MEMORY_COST,
    parallelism=settings.ARGON2_PARALLELISM,
    hash_len=32,
    salt_len=16,
)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify *plain* against an Argon2 *hashed* string."""
    try:
        ph.verify(hashed, plain)
        return True
    except (VerifyMismatchError, InvalidHashError):
        return False


def hash_password(password: str) -> str:
    """Return an Argon2 hash for *password*."""
    return ph.hash(password)


# ── User authentication (sync — used by Flask) ──────────────────

def authenticate_user(
    db: Session, username: str, password: str
) -> Optional[Dict[str, Any]]:
    """
    Authenticate *username* / *password* against camet_global.

    Returns a dict with user+tenant info on success, ``None`` on failure.
    The dict contains everything needed to populate ``session["user"]``.
    """
    try:
        stmt = (
            select(User, Tenant)
            .join(Tenant, User.tenant_id == Tenant.tenant_id)
            .where(User.username == username)
        )
        result = db.execute(stmt).first()

        if result is None:
            return None

        user, tenant = result

        if not tenant.is_active:
            return None

        if not verify_password(password, user.password):
            return None

        # Parse tenant config to find the client db_name
        tenant_config = tenant.config_tenant or {}
        db_name = tenant_config.get("db_name", "")

        return {
            "user_id": user.user_id,
            "username": user.username,
            "email": user.email,
            "tenant_id": user.tenant_id,
            "role": user.role,
            "permissions": user.permissions or {},
            "tenant_info": {
                "company_name": tenant.company_name,
                "config": tenant_config,
                "db_name": db_name,
            },
        }
    except Exception as exc:
        print(f"[AUTH] Authentication error: {exc}")
        return None


def get_user_by_id(
    db: Session, user_id: int
) -> Optional[Dict[str, Any]]:
    """Retrieve user info by *user_id* (session revalidation)."""
    try:
        stmt = (
            select(User, Tenant)
            .join(Tenant, User.tenant_id == Tenant.tenant_id)
            .where(User.user_id == user_id)
        )
        result = db.execute(stmt).first()
        if result is None:
            return None

        user, tenant = result
        if not tenant.is_active:
            return None

        tenant_config = tenant.config_tenant or {}
        return {
            "user_id": user.user_id,
            "username": user.username,
            "email": user.email,
            "tenant_id": user.tenant_id,
            "role": user.role,
            "permissions": user.permissions or {},
            "tenant_info": {
                "company_name": tenant.company_name,
                "config": tenant_config,
                "db_name": tenant_config.get("db_name", ""),
            },
        }
    except Exception as exc:
        print(f"[AUTH] User lookup error: {exc}")
        return None
