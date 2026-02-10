"""
Authentication Routes
Handles login, logout, and session management
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import datetime

from app.core.config import settings
from app.core.database import db_manager
from app.core.auth_utils import authenticate_user
from app.models.global_models import UserLogin


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """
    Login page and form handler.
    Authenticates against camet_global database.
    """
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        if not username or not password:
            flash("Por favor ingrese usuario y contraseña", "error")
            return render_template("auth/login.html")
        
        # Authenticate against database
        with db_manager.get_global_session_sync() as db:
            user_info = authenticate_user(db, username, password)
            
            if user_info is None:
                flash("Usuario o contraseña incorrectos", "error")
                return render_template("auth/login.html")
            
            # Store user info in session
            session["user"] = {
                "user_id": user_info["user_id"],
                "username": user_info["username"],
                "email": user_info["email"],
                "tenant_id": user_info["tenant_id"],
                "role": user_info["role"],
                "permissions": user_info["permissions"],
                "tenant_info": user_info["tenant_info"]
            }
            
            # Log the login (optional, for audit trail)
            try:
                login_record = UserLogin(
                    user_id=user_info["user_id"],
                    username=user_info["username"],
                    ip_address=request.remote_addr or "unknown",
                    user_agent=request.headers.get("User-Agent", "")[:255]
                )
                db.add(login_record)
                db.commit()
                
                # Store login_id in session for logout tracking
                session["login_id"] = login_record.login_id
            except Exception as e:
                # Don't fail login if audit logging fails
                print(f"Failed to log login: {e}")
            
            flash(f"Bienvenido, {user_info['username']}!", "success")
            return redirect(url_for("dashboard.index"))
    
    return render_template("auth/login.html")


@auth_bp.route("/logout")
def logout():
    """
    Logout and clear session.
    Updates logout timestamp in user_login table.
    """
    # Update logout timestamp if we have login_id
    login_id = session.get("login_id")
    if login_id:
        try:
            with db_manager.get_global_session_sync() as db:
                login_record = db.query(UserLogin).filter_by(login_id=login_id).first()
                if login_record:
                    login_record.logout_at = datetime.utcnow()
                    db.commit()
        except Exception as e:
            print(f"Failed to update logout timestamp: {e}")
    
    session.clear()
    flash("Sesión cerrada exitosamente", "info")
    return redirect(url_for("auth.login"))


def login_required(f):
    """
    Decorator to require login for a route.
    """
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            flash("Por favor inicie sesión", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    
    return decorated_function


def get_current_user():
    """
    Get current user from session.
    """
    return session.get("user")
