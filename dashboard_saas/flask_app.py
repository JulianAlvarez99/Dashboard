"""
Flask application factory.

Phase 1: minimal — no CSRF, no security headers, no auth.
Just serves the dashboard HTML via Jinja2.
"""

from flask import Flask, redirect, url_for
from dashboard_saas.core.config import settings


def create_flask_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    # Minimal Flask config
    app.config["SECRET_KEY"] = settings.FLASK_SECRET_KEY or "dev-secret-key"
    app.config["DEBUG"] = settings.DEBUG
    app.config["API_BASE_URL"] = settings.API_BASE_URL

    # ── Register Blueprints ─────────────────────────────────────
    from dashboard_saas.routes.dashboard import dashboard_bp
    app.register_blueprint(dashboard_bp)

    # ── Root redirect → /dashboard/ ─────────────────────────────
    @app.route("/")
    def index():
        return redirect(url_for("dashboard.index"))

    # ── Error handlers ──────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        return _render_error(404, "Página no encontrada"), 404

    @app.errorhandler(500)
    def server_error(e):
        return _render_error(500, "Error interno del servidor"), 500

    return app


def _render_error(code: int, message: str) -> str:
    """Simple error page (no template dependency)."""
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


# Module-level instance (used by run_dashboard_saas.py)
flask_app = create_flask_app()
