from flask import Flask, render_template, redirect, url_for
from flask_cors import CORS
from flask_login import LoginManager, login_required, current_user
from config import Config
from auth_manager import AuthManager 
import os

def create_app():
    # Inicializamos Flask
    app = Flask(__name__)
    
    # Habilitamos CORS (permite que una web en otro dominio/puerto consuma esta API)
    CORS(app)
    
    # Configuraciones básicas
    app.config.from_object(Config)

    # --- CONFIGURACIÓN DE LOGIN ---
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login' # Redirigir aquí si no está logueado
    login_manager.login_message = "Por favor inicia sesión para acceder al dashboard."
    login_manager.login_message_category = "warning"

    # Función para recargar usuario desde la sesión
    @login_manager.user_loader
    def load_user(user_id):
        return AuthManager.get_user_by_id(user_id)

    # --- REGISTRO DE BLUEPRINTS ---
    from auth_routes import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from routes import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    # --- RUTA PRINCIPAL (Protegida) ---
    @app.route('/')
    @login_required
    def index():
        # Pasamos el usuario actual al template para mostrar "Hola, Julian"
        return render_template('index.html', user=current_user)

    return app

# Instancia de la aplicación (necesaria para WSGI/Cpanel)
application = create_app()
app = application # Alias común

if __name__ == '__main__':
    debug_mode = os.getenv('APP_ENV', 'local') == 'local'
    port = int(os.getenv('PORT', 5000))
    print(f"--- Servidor iniciando en puerto {port} ---")
    app.run(host='0.0.0.0', port=port, debug=debug_mode)