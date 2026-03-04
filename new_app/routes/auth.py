"""
Authentication routes — Login, Logout, session management.

After successful login the session stores:
  session["user"]     → dict with user/tenant info
  session["login_id"] → for logout audit
  session["db_name"]  → tenant database name (for cache & queries)
"""

import logging
import threading
import time
from datetime import datetime, timezone
from functools import wraps

from flask import (
    Blueprint, flash, redirect, render_template,
    request, session, url_for,
)

import httpx

from new_app.core.auth import authenticate_user
from new_app.core.config import get_settings
from new_app.core.database import db_manager
from new_app.core.jwt_utils import create_access_token
from new_app.core.limiter import rate_limit
from new_app.models.global_models import UserLogin

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


# ── Decorators ───────────────────────────────────────────────────

def login_required(f):
    """Redirect to /auth/login if no active session."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            flash("Inicie sesión para continuar", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


def role_required(*roles: str):
    """
    Decorator (Flask): verify the session user has one of the required roles.

    Must be applied **after** a route decorator and combines with
    ``login_required`` — unauthenticated requests are redirected to login.

    Usage::

        @dashboard_bp.route("/admin")
        @role_required("ADMIN", "MANAGER")
        def admin_view():
            ...
    """
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user or user.get("role") not in roles:
                flash("No tiene permisos para acceder a esta sección.", "error")
                return redirect(url_for("dashboard.index"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def get_current_user() -> dict | None:
    """Return ``session["user"]`` or ``None``."""
    return session.get("user")


# ── Private helpers ──────────────────────────────────────────────

def _build_session(user_info: dict, login_id: int) -> None:
    """Populate the Flask session with user data.

    Calls ``session.clear()`` first to prevent session fixation attacks:
    an attacker who possesses a pre-login session ID cannot reuse it
    after the user authenticates.
    """
    session.clear()
    session["user"] = user_info
    session["db_name"] = user_info["tenant_info"].get("db_name", "")
    session["login_id"] = login_id


def _warmup_cache(db_name: str, api_internal_key: str, api_base_url: str,
                  tenant_id: int = 0, role: str = "ADMIN") -> None:
    """Send the cache-load request to FastAPI in a background thread.

    Running this in a daemon thread means the user's login response is NOT
    blocked while the cache warms up (which can take several seconds on
    cold start).  Retries up to 5 times with exponential back-off so a
    slow FastAPI start-up does not permanently break the first session.
    """
    url = f"{api_base_url}/api/v1/system/cache/load/{db_name}"
    max_retries = 3
    delays = [1, 2, 4]  # seconds — short schedule, no need for deep back-off
    for attempt in range(1, max_retries + 1):
        try:
            resp = httpx.post(
                url,
                headers={"X-Internal-Key": api_internal_key},
                timeout=30.0,
            )
            if resp.status_code == 200:
                logger.info("[AUTH] Cache loaded for tenant '%s'", db_name)
                # ── Warm up layout cache ──────────────────────────────
                if tenant_id:
                    try:
                        layout_url = (
                            f"{api_base_url}/api/v1/layout/config"
                            f"?tenant_id={tenant_id}&role={role}"
                        )
                        layout_resp = httpx.get(layout_url, timeout=10.0)
                        if layout_resp.status_code == 200:
                            from new_app.core.cache import metadata_cache  # noqa: PLC0415
                            metadata_cache.set_layout(tenant_id, role, layout_resp.json())
                            logger.info(
                                "[AUTH] Layout cached for tenant=%s role=%s",
                                tenant_id, role,
                            )
                    except Exception as exc:
                        logger.warning("[AUTH] Layout cache warmup failed: %s", exc)
                return
            logger.warning(
                "[AUTH] Cache load returned %s for tenant '%s' (attempt %d/%d)",
                resp.status_code, db_name, attempt, max_retries,
            )
        except Exception as exc:
            logger.warning(
                "[AUTH] Cache warm-up failed for '%s' (attempt %d/%d): %s",
                db_name, attempt, max_retries, exc,
            )
        if attempt < max_retries:
            time.sleep(delays[attempt - 1])  # 1, 2 s (index 0-based)
    logger.error("[AUTH] Cache warm-up exhausted %d retries for '%s'", max_retries, db_name)


# ── Routes ───────────────────────────────────────────────────────

@auth_bp.route("/login", methods=["GET", "POST"])
@rate_limit(max_calls=10, window_seconds=60)
def login():
    if request.method == "GET":
        return render_template("auth/login.html")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    if not username or not password:
        flash("Ingrese usuario y contraseña", "error")
        return render_template("auth/login.html")

    settings = get_settings()

    with db_manager.get_global_session_sync() as db:
        try:
            user_info = authenticate_user(db, username, password)
        except RuntimeError:
            # DB unavailable — raised by authenticate_user on OperationalError
            flash("Error de conexión. Intente más tarde.", "error")
            return render_template("auth/login.html")

        if user_info is None:
            flash("Usuario o contraseña incorrectos", "error")
            logger.warning(
                "[AUTH] Failed login attempt for '%s' from %s",
                username, request.remote_addr,
            )
            # Audit: record failed attempt
            try:
                from new_app.services.audit.audit_service import audit_service  # noqa: PLC0415
                with db_manager.get_global_session_sync() as _db:
                    audit_service.log_login_failure(
                        db=_db,
                        username=username,
                        ip=request.remote_addr or "unknown",
                        reason="invalid_credentials",
                    )
            except Exception as _exc:
                logger.error("[AUTH] AuditLog (login failure) failed: %s", _exc)
            return render_template("auth/login.html")

        # ── Audit: record login session ──────────────────────
        login_id = 0
        try:
            login_record = UserLogin(
                user_id=user_info["user_id"],
                username=user_info["username"],
                ip_address=request.remote_addr or "unknown",
                user_agent=request.headers.get("User-Agent", "")[:255],
            )
            db.add(login_record)
            db.commit()
            login_id = login_record.login_id
        except Exception as exc:
            logger.error("[AUTH] UserLogin record failed: %s", exc)

    # ── Write AuditLog (LOGIN_SUCCESS) ───────────────────────
    try:
        from new_app.services.audit.audit_service import audit_service  # noqa: PLC0415
        with db_manager.get_global_session_sync() as db:
            audit_service.log_login_success(
                db=db,
                user_id=user_info["user_id"],
                ip=request.remote_addr or "unknown",
                user_agent=request.headers.get("User-Agent", "")[:255],
                tenant_id=user_info["tenant_id"],
                username=user_info["username"],
            )
    except Exception as exc:
        logger.error("[AUTH] AuditLog write failed: %s", exc)

    # ── Populate session (session.clear() prevents session fixation) ─
    _build_session(user_info, login_id)
    # ── Issue JWT for FastAPI calls ───────────────────────────
    try:
        access_token = create_access_token(
            user_id=user_info["user_id"],
            username=user_info["username"],
            role=user_info["role"],
            db_name=user_info["tenant_info"]["db_name"],
            tenant_id=user_info["tenant_id"],
        )
        session["access_token"] = access_token
    except Exception as exc:
        logger.error("[AUTH] JWT creation failed: %s", exc)
        # Non-fatal: user is logged in via session; FastAPI calls will fail
        # until the token issue is resolved (e.g., JWT_SECRET_KEY missing).
    # ── Cache warm-up: non-blocking daemon thread ────────────
    db_name = session["db_name"]
    if db_name:
        threading.Thread(
            target=_warmup_cache,
            args=(db_name, settings.API_INTERNAL_KEY, settings.API_BASE_URL),
            kwargs={
                "tenant_id": user_info["tenant_id"],
                "role": user_info.get("role", "ADMIN"),
            },
            daemon=True,
        ).start()

    flash(f"Bienvenido, {user_info['username']}!", "success")
    return redirect(url_for("dashboard.index"))


@auth_bp.route("/logout")
def logout():
    login_id = session.get("login_id")
    user_info = session.get("user")

    # ── Audit: record logout timestamp on UserLogin row ──────
    if login_id:
        try:
            with db_manager.get_global_session_sync() as db:
                rec = db.query(UserLogin).filter_by(login_id=login_id).first()
                if rec:
                    rec.logout_at = datetime.now(timezone.utc)
                    db.commit()
        except Exception as exc:
            logger.error("[AUTH] Logout audit (UserLogin) failed: %s", exc)

    # ── Write AuditLog (LOGOUT) ──────────────────────────────
    if user_info:
        try:
            from new_app.services.audit.audit_service import audit_service  # noqa: PLC0415
            with db_manager.get_global_session_sync() as db:
                audit_service.log_logout(
                    db=db,
                    user_id=user_info["user_id"],
                    ip=request.remote_addr or "unknown",
                    username=user_info["username"],
                )
        except Exception as exc:
            logger.error("[AUTH] AuditLog write (logout) failed: %s", exc)

    session.clear()
    flash("Sesión cerrada exitosamente", "info")
    return redirect(url_for("auth.login"))
