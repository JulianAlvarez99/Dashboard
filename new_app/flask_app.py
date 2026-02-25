"""
Flask application factory.

Responsibilities:
- Jinja2 SSR (server-side rendering) of HTML templates.
- Session-based authentication (Argon2 + server-side sessions).
- Proxy / redirect to FastAPI when the browser needs data.
"""

from flask import Flask, redirect, url_for
from flask_wtf.csrf import CSRFProtect

from new_app.core.config import settings

# CSRF protection singleton — init_app(app) called inside create_flask_app()
csrf = CSRFProtect()


def create_flask_app() -> Flask:
    """Application factory for Flask."""
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    app.config["SECRET_KEY"] = settings.FLASK_SECRET_KEY
    app.config["DEBUG"] = settings.DEBUG
    app.config["API_BASE_URL"] = settings.API_BASE_URL
    # Flask-WTF CSRF
    app.config["WTF_CSRF_ENABLED"] = True
    app.config["WTF_CSRF_TIME_LIMIT"] = 3600  # token valid 1 hour

    # ── CSRF protection ──────────────────────────────────────
    csrf.init_app(app)

    # ── Blueprints ───────────────────────────────────────────
    from new_app.routes.auth import auth_bp
    from new_app.routes.dashboard import dashboard_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)

    # ── Root redirect ────────────────────────────────────────
    @app.route("/")
    def index():
        return redirect(url_for("dashboard.index"))

    # ── Error handlers ───────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        return _render_error(404, "Página no encontrada"), 404

    @app.errorhandler(500)
    def server_error(e):
        return _render_error(500, "Error interno del servidor"), 500

    @app.errorhandler(403)
    def forbidden(e):
        return _render_error(403, "Acceso denegado"), 403

    # ── Security headers ─────────────────────────────────────
    @app.after_request
    def set_security_headers(response):
        """
        Inject hardening headers on every Flask response.

        X-Frame-Options      — prevent clickjacking.
        X-Content-Type-Options — prevent MIME sniffing.
        Referrer-Policy      — limit referrer info on cross-origin navigation.
        Permissions-Policy   — disable powerful browser APIs not used here.
        Content-Security-Policy — restrict resource origins.

        connect-src includes API_BASE_URL so the browser JS (api-client.js)
        can reach FastAPI.  For production, restrict this to the real domain.
        """
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-XSS-Protection", "1; mode=block")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=(), interest-cohort=()",
        )
        api_base = app.config.get("API_BASE_URL", "")
        connect_src = f"'self' {api_base}".strip()
        response.headers.setdefault(
            "Content-Security-Policy",
            (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
                "https://cdn.tailwindcss.com https://cdn.jsdelivr.net https://unpkg.com; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com data:; "
                "img-src 'self' data: blob:; "
                f"connect-src {connect_src};"
            ),
        )
        return response

    return app


def _render_error(code: int, message: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Error {code}</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-900 min-h-screen flex items-center justify-center">
  <div class="text-center">
    <h1 class="text-6xl font-bold text-white">{code}</h1>
    <p class="mt-4 text-xl text-gray-400">{message}</p>
    <a href="/" class="mt-8 inline-block px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
      Volver al inicio
    </a>
  </div>
</body>
</html>"""


# Module-level instance for direct use
flask_app = create_flask_app()
