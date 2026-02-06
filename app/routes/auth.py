"""
Authentication Routes
Handles login, logout, and session management
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import httpx

from app.core.config import settings


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """
    Login page and form handler.
    """
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        if not username or not password:
            flash("Por favor ingrese usuario y contraseña", "error")
            return render_template("auth/login.html")
        
        # TODO: Implement actual authentication via FastAPI
        # For now, simulate successful login for development
        if settings.DEBUG and username == "admin":
            session["user"] = {
                "user_id": 1,
                "username": username,
                "tenant_id": 1,
                "role": "ADMIN"
            }
            flash("Inicio de sesión exitoso", "success")
            return redirect(url_for("dashboard.index"))
        
        flash("Usuario o contraseña incorrectos", "error")
        return render_template("auth/login.html")
    
    return render_template("auth/login.html")


@auth_bp.route("/logout")
def logout():
    """
    Logout and clear session.
    """
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
