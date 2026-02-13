"""
Authentication routes — Login, Logout, session management.

After successful login the session stores:
  session["user"]     → dict with user/tenant info
  session["login_id"] → for logout audit
  session["db_name"]  → tenant database name (for cache & queries)
"""

from datetime import datetime
from functools import wraps

from flask import (
    Blueprint, flash, redirect, render_template,
    request, session, url_for,
)

import httpx

from new_app.core.auth import authenticate_user
from new_app.core.config import get_settings
from new_app.core.database import db_manager
from new_app.models.global_models import UserLogin

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


def get_current_user() -> dict | None:
    """Return ``session["user"]`` or ``None``."""
    return session.get("user")


# ── Routes ───────────────────────────────────────────────────────

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("auth/login.html")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    if not username or not password:
        flash("Ingrese usuario y contraseña", "error")
        return render_template("auth/login.html")

    with db_manager.get_global_session_sync() as db:
        user_info = authenticate_user(db, username, password)

        if user_info is None:
            flash("Usuario o contraseña incorrectos", "error")
            return render_template("auth/login.html")

        # ── Populate session ────────────────────────────────
        session["user"] = user_info
        session["db_name"] = user_info["tenant_info"].get("db_name", "")

        # ── Audit login ─────────────────────────────────────
        try:
            login_record = UserLogin(
                user_id=user_info["user_id"],
                username=user_info["username"],
                ip_address=request.remote_addr or "unknown",
                user_agent=request.headers.get("User-Agent", "")[:255],
            )
            db.add(login_record)
            db.commit()
            session["login_id"] = login_record.login_id
        except Exception as exc:
            print(f"[AUTH] Audit log failed: {exc}")

    # ── Trigger cache load for this tenant (via FastAPI) ──
    db_name = session["db_name"]
    if db_name:
        try:
            settings = get_settings()
            api_url = f"{settings.API_BASE_URL}/api/v1/system/cache/load/{db_name}"
            resp = httpx.post(api_url, timeout=15.0)
            if resp.status_code == 200:
                print(f"[AUTH] Cache loaded for tenant '{db_name}'")
            else:
                print(f"[AUTH] Cache load returned {resp.status_code}")
        except Exception as exc:
            print(f"[AUTH] Cache load request failed: {exc}")

    flash(f"Bienvenido, {user_info['username']}!", "success")
    return redirect(url_for("dashboard.index"))


@auth_bp.route("/logout")
def logout():
    login_id = session.get("login_id")
    if login_id:
        try:
            with db_manager.get_global_session_sync() as db:
                rec = db.query(UserLogin).filter_by(login_id=login_id).first()
                if rec:
                    rec.logout_at = datetime.utcnow()
                    db.commit()
        except Exception as exc:
            print(f"[AUTH] Logout audit failed: {exc}")

    session.clear()
    flash("Sesión cerrada exitosamente", "info")
    return redirect(url_for("auth.login"))
