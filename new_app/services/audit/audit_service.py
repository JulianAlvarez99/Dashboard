"""
AuditLogService — Security event audit trail.

Single Responsibility: write security events to the ``audit_log`` table.

Supported actions:
  LOGIN_SUCCESS  — successful authentication
  LOGIN_FAILURE  — bad credentials or inactive tenant
  LOGOUT         — explicit logout

Design notes:
  - ``user_id = 0`` is the convention for "unknown/anonymous" in login
    failures where the username was not found in the DB.  This avoids
    an ALTER TABLE migration on ``audit_log.user_id NOT NULL``.
  - All writes are fire-and-forget from the caller's perspective: the
    caller wraps the call in try/except so an audit failure never blocks
    the user's request.
  - ``details`` (longtext) stores a JSON-serialised dict with contextual
    metadata for the event.
"""

import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from new_app.models.global_models import AuditLog

logger = logging.getLogger(__name__)

# Sentinel user_id used when the real user could not be resolved
# (e.g. username does not exist during a login attempt).
ANONYMOUS_USER_ID = 0


class AuditLogService:
    """Writes security events to ``audit_log``."""

    # ── Public API ────────────────────────────────────────────────

    def log_login_success(
        self,
        db: Session,
        user_id: int,
        ip: str,
        user_agent: str,
        tenant_id: int,
        username: str,
    ) -> None:
        """Record a successful authentication."""
        self._write(
            db=db,
            user_id=user_id,
            action="LOGIN_SUCCESS",
            ip=ip,
            details={
                "username": username,
                "tenant_id": tenant_id,
                "user_agent": user_agent,
            },
        )

    def log_login_failure(
        self,
        db: Session,
        username: str,
        ip: str,
        reason: str,
        user_id: Optional[int] = None,
    ) -> None:
        """Record a failed authentication attempt.

        Args:
            user_id: Use the real user_id if the account exists but the
                password is wrong.  Pass ``None`` (maps to
                ``ANONYMOUS_USER_ID = 0``) when the username was not
                found in the DB at all.
            reason:  Short description, e.g. "bad_credentials",
                "inactive_tenant".
        """
        self._write(
            db=db,
            user_id=user_id if user_id is not None else ANONYMOUS_USER_ID,
            action="LOGIN_FAILURE",
            ip=ip,
            details={
                "attempted_username": username,
                "reason": reason,
            },
        )

    def log_logout(
        self,
        db: Session,
        user_id: int,
        ip: str,
        username: str,
    ) -> None:
        """Record an explicit logout."""
        self._write(
            db=db,
            user_id=user_id,
            action="LOGOUT",
            ip=ip,
            details={"username": username},
        )

    # ── Private ───────────────────────────────────────────────────

    def _write(
        self,
        db: Session,
        user_id: int,
        action: str,
        ip: str,
        details: dict,
    ) -> None:
        """Persist one ``AuditLog`` row.  Silently logs on DB error."""
        try:
            record = AuditLog(
                user_id=user_id,
                action=action,
                ip_address=ip[:45],
                details=json.dumps(details, ensure_ascii=False),
            )
            db.add(record)
            db.commit()
            logger.debug("[AuditLog] %s user_id=%s ip=%s", action, user_id, ip)
        except Exception as exc:
            logger.error(
                "[AuditLog] Failed to write '%s' event: %s", action, exc
            )
            db.rollback()


# ── Singleton ─────────────────────────────────────────────────────
audit_service = AuditLogService()
