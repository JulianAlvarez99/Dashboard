"""
Flask Application for Server-Side Rendering
Handles HTML pages, authentication, and static files
"""

from flask import Flask, redirect, url_for

from app.core.config import settings


def create_flask_app() -> Flask:
    """
    Application factory for Flask.
    """
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static"
    )
    
    # Configuration
    app.config["SECRET_KEY"] = settings.FLASK_SECRET_KEY
    app.config["DEBUG"] = settings.DEBUG
    app.config["API_BASE_URL"] = settings.API_BASE_URL
    
    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    
    # Root redirect
    @app.route("/")
    def index():
        return redirect(url_for("dashboard.index"))
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return render_error(404, "Página no encontrada"), 404
    
    @app.errorhandler(500)
    def server_error(e):
        return render_error(500, "Error interno del servidor"), 500
    
    @app.errorhandler(403)
    def forbidden(e):
        return render_error(403, "Acceso denegado"), 403
    
    return app


def render_error(code: int, message: str) -> str:
    """Render a simple error page"""
    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Error {code}</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-100 dark:bg-gray-900 min-h-screen flex items-center justify-center">
        <div class="text-center">
            <h1 class="text-6xl font-bold text-gray-800 dark:text-white">{code}</h1>
            <p class="mt-4 text-xl text-gray-600 dark:text-gray-400">{message}</p>
            <a href="/" class="mt-8 inline-block px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                Volver al inicio
            </a>
        </div>
    </body>
    </html>
    """


# Create app instance
flask_app = create_flask_app()


if __name__ == "__main__":
    flask_app.run(
        host="0.0.0.0",
        port=settings.FLASK_PORT,
        debug=settings.DEBUG
    )
