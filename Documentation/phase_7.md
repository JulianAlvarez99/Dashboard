# AGENTS.MD - FASE 7: Frontend con Flask + Jinja2 + HTMX

## 🎯 OBJETIVO DE LA FASE 7

Implementar el frontend completo del dashboard usando Flask para server-side rendering, Jinja2 para templates, HTMX para interactividad sin JavaScript pesado, Alpine.js para lógica reactiva mínima, Chart.js para visualizaciones y Tailwind CSS para styling moderno.

**Duración Estimada:** 2 semanas  
**Prioridad:** Alta (interfaz de usuario principal)

**PRINCIPIO FUNDAMENTAL:** El frontend consume la API FastAPI para obtener datos y renderiza la UI dinámicamente según la configuración de WIDGET_CATALOG y DASHBOARD_TEMPLATE.

---

## 📦 TASK 7.1: Configuración de Flask y Estructura Base

### Descripción
Configurar Flask con todas las extensiones necesarias, establecer la estructura de templates base con Jinja2, integrar Tailwind CSS, HTMX, Alpine.js y Chart.js.

### Criterios de Aceptación
- Flask configurado con CSRF protection
- Cliente HTTP async (httpx) para comunicación con FastAPI
- Sistema de sesiones funcionando
- Base template con dark mode y responsive design
- CDNs de Tailwind, HTMX, Alpine.js y Chart.js cargados
- Sistema de toast notifications implementado

### Archivos a Crear

**app/wsgi.py** (Flask Application):
```python
"""
Flask WSGI application entry point
"""
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
from flask_wtf.csrf import CSRFProtect
import httpx
from functools import wraps
import os
from dotenv import load_dotenv
from datetime import timedelta
import asyncio

load_dotenv()

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY')
app.config['API_BASE_URL'] = os.getenv('API_BASE_URL', 'http://localhost:8000')
app.config['SESSION_COOKIE_SECURE'] = os.getenv('ENV') == 'production'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=int(os.getenv('SESSION_TIMEOUT_MINUTES', '30')))

# CSRF Protection
csrf = CSRFProtect(app)

# HTTP Client for API communication
http_client = httpx.AsyncClient(
    base_url=app.config['API_BASE_URL'],
    timeout=30.0
)

def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'access_token' not in session:
            flash('Por favor inicie sesión para acceder a esta página', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def async_route(f):
    """Decorator to handle async routes in Flask"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper

@app.context_processor
def inject_user():
    """Inject user data into all templates"""
    return dict(user=session.get('user'))

@app.errorhandler(404)
def not_found(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('errors/500.html'), 500

@app.errorhandler(403)
def forbidden(error):
    return render_template('errors/403.html'), 403

# Import routes
from app.routes import auth, dashboard, admin

# Register blueprints
app.register_blueprint(auth.bp)
app.register_blueprint(dashboard.bp)
app.register_blueprint(admin.bp)

@app.route('/')
def index():
    """Root route - redirect to dashboard or login"""
    if 'access_token' in session:
        return redirect(url_for('dashboard.index'))
    return redirect(url_for('auth.login'))

if __name__ == '__main__':
    app.run(
        debug=os.getenv('DEBUG', 'False') == 'True',
        port=int(os.getenv('FLASK_PORT', '5000')),
        host='0.0.0.0'
    )
```

**app/routes/__init__.py**:
```python
"""
Flask routes package
"""
```

**app/routes/auth.py**:
```python
"""
Authentication routes
"""
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app.wsgi import http_client, async_route
import httpx

bp = Blueprint('auth', __name__, url_prefix='/auth')

@bp.route('/login', methods=['GET', 'POST'])
@async_route
async def login():
    """Login page and handler"""
    if 'access_token' in session:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        try:
            response = await http_client.post('/api/v1/auth/login', json={
                'username': username,
                'password': password
            })
            
            if response.status_code == 200:
                data = response.json()
                session.permanent = True
                session['access_token'] = data['access_token']
                session['refresh_token'] = data['refresh_token']
                session['user'] = data['user']
                
                flash(f'¡Bienvenido, {data["user"]["username"]}!', 'success')
                
                next_page = request.args.get('next')
                return redirect(next_page if next_page else url_for('dashboard.index'))
            else:
                flash('Credenciales inválidas. Por favor intente nuevamente.', 'error')
        except httpx.RequestError as e:
            flash('Error de conexión con el servidor. Por favor intente más tarde.', 'error')
        except Exception as e:
            flash('Ha ocurrido un error inesperado.', 'error')
    
    return render_template('auth/login.html')

@bp.route('/logout')
@async_route
async def logout():
    """Logout handler"""
    if 'access_token' in session:
        try:
            headers = {'Authorization': f"Bearer {session['access_token']}"}
            await http_client.post('/api/v1/auth/logout', headers=headers)
        except:
            pass  # Ignore errors on logout
    
    session.clear()
    flash('Sesión cerrada correctamente', 'info')
    return redirect(url_for('auth.login'))
```

**app/templates/base.html**:
```html
<!DOCTYPE html>
<html class="dark" lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Dashboard - Camet Analytics{% endblock %}</title>
    
    <!-- Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
    
    <!-- Google Fonts: Inter -->
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet"/>
    
    <!-- Material Symbols -->
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet"/>
    
    <!-- Tailwind Configuration -->
    <script>
        tailwind.config = {
            darkMode: "class",
            theme: {
                extend: {
                    colors: {
                        "primary": "#2b7cee",
                        "primary-dark": "#1a5bb5",
                        "background-light": "#F3F4F6",
                        "background-dark": "#0f172a",
                        "surface-light": "#FFFFFF",
                        "surface-dark": "#1e293b",
                        "text-main": "#1e293b",
                        "text-sub": "#64748b",
                        "border-light": "#e2e8f0",
                    },
                    fontFamily: {
                        "display": ["Inter", "sans-serif"],
                        "body": ["Inter", "sans-serif"],
                    },
                },
            },
        }
    </script>
    
    <!-- Custom Styles -->
    <style>
        body { font-family: 'Inter', sans-serif; }
        
        .custom-scrollbar::-webkit-scrollbar { width: 4px; height: 4px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background-color: #cbd5e1; border-radius: 20px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background-color: #94a3b8; }
        
        .icon-filled { font-variation-settings: 'FILL' 1, 'wght' 400, 'GRAD' 0, 'opsz' 24; }
        
        .htmx-indicator { display: none; }
        .htmx-request .htmx-indicator { display: inline-block; }
        
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        .animate-spin { animation: spin 1s linear infinite; }
        
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        .fade-in { animation: fadeIn 0.3s ease-out; }
    </style>
    
    <meta name="csrf-token" content="{{ csrf_token() }}">
    {% block extra_head %}{% endblock %}
</head>
<body class="bg-background-light dark:bg-background-dark text-text-main dark:text-gray-100">
    {% block body %}{% endblock %}
    
    <!-- Toast Notifications Container -->
    <div id="toast-container" class="fixed top-4 right-4 z-50 space-y-2"></div>
    
    <!-- Flash Messages -->
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            <script>
                window.addEventListener('DOMContentLoaded', function() {
                    {% for category, message in messages %}
                        showToast('{{ message }}', '{{ category }}');
                    {% endfor %}
                });
            </script>
        {% endif %}
    {% endwith %}
    
    <!-- Alpine.js -->
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.13.3/dist/cdn.min.js"></script>
    
    <!-- HTMX -->
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    
    <!-- Chart.js -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    
    <!-- Global Scripts -->
    <script>
        // Configure HTMX with CSRF Token
        document.body.addEventListener('htmx:configRequest', (event) => {
            const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
            event.detail.headers['X-CSRFToken'] = csrfToken;
        });
        
        // Toast Notification System
        function showToast(message, type = 'info') {
            const container = document.getElementById('toast-container');
            const toast = document.createElement('div');
            const colors = {
                'success': 'bg-green-500',
                'error': 'bg-red-500',
                'warning': 'bg-yellow-500',
                'info': 'bg-blue-500'
            };
            const icons = {
                'success': 'check_circle',
                'error': 'error',
                'warning': 'warning',
                'info': 'info'
            };
            
            toast.className = `${colors[type]} text-white px-6 py-4 rounded-lg shadow-lg flex items-center gap-3 min-w-[300px] fade-in`;
            toast.innerHTML = `
                <span class="material-symbols-outlined">${icons[type]}</span>
                <span class="flex-1">${message}</span>
                <button onclick="this.parentElement.remove()" class="hover:bg-white/20 rounded p-1">
                    <span class="material-symbols-outlined text-[18px]">close</span>
                </button>
            `;
            
            container.appendChild(toast);
            setTimeout(() => {
                toast.style.opacity = '0';
                toast.style.transform = 'translateX(100%)';
                toast.style.transition = 'all 0.3s ease-out';
                setTimeout(() => toast.remove(), 300);
            }, 5000);
        }
        
        // Global error handler for HTMX
        document.body.addEventListener('htmx:responseError', (event) => {
            showToast('Error al cargar los datos. Intente nuevamente.', 'error');
        });
    </script>
    
    {% block scripts %}{% endblock %}
</body>
</html>
```

### Verificación
```bash
# 1. Crear estructura de directorios
mkdir -p app/routes app/templates/{auth,dashboard,admin,errors}

# 2. Instalar dependencias adicionales
pip install flask flask-wtf httpx

# 3. Iniciar Flask
python app/wsgi.py

# 4. Verificar en navegador
# http://localhost:5000
```

---

## 📦 TASK 7.2: Templates de Autenticación

### Descripción
Crear templates para login/logout con diseño moderno, validación de formularios y mensajes de error.

### Criterios de Aceptación
- Login page responsivo y accesible
- Validación de campos en frontend
- Mensajes de error claros
- Redirección correcta después del login

### Archivos a Crear

**app/templates/auth/login.html**:
```html
{% extends "base.html" %}

{% block title %}Iniciar Sesión - Dashboard{% endblock %}

{% block body %}
<div class="min-h-screen flex items-center justify-center px-4 py-12 bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-gray-900 dark:to-gray-800">
    <div class="max-w-md w-full space-y-8">
        <!-- Logo y Título -->
        <div class="text-center">
            <div class="mx-auto h-16 w-16 bg-primary rounded-full flex items-center justify-center mb-4">
                <span class="material-symbols-outlined text-white text-3xl icon-filled">monitoring</span>
            </div>
            <h2 class="text-3xl font-bold text-gray-900 dark:text-white">
                Dashboard Industrial
            </h2>
            <p class="mt-2 text-sm text-gray-600 dark:text-gray-400">
                Ingrese sus credenciales para continuar
            </p>
        </div>
        
        <!-- Formulario de Login -->
        <div class="bg-white dark:bg-surface-dark rounded-xl shadow-2xl p-8">
            <form method="POST" action="{{ url_for('auth.login') }}" class="space-y-6">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
                
                <!-- Username -->
                <div>
                    <label for="username" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Usuario
                    </label>
                    <div class="relative">
                        <span class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                            <span class="material-symbols-outlined text-gray-400">person</span>
                        </span>
                        <input 
                            type="text" 
                            name="username" 
                            id="username" 
                            required 
                            autofocus
                            class="block w-full pl-10 pr-3 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-colors"
                            placeholder="Ingrese su usuario"
                        />
                    </div>
                </div>
                
                <!-- Password -->
                <div>
                    <label for="password" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Contraseña
                    </label>
                    <div class="relative">
                        <span class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                            <span class="material-symbols-outlined text-gray-400">lock</span>
                        </span>
                        <input 
                            type="password" 
                            name="password" 
                            id="password" 
                            required
                            class="block w-full pl-10 pr-3 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-colors"
                            placeholder="Ingrese su contraseña"
                        />
                    </div>
                </div>
                
                <!-- Submit Button -->
                <button 
                    type="submit" 
                    class="w-full flex items-center justify-center gap-2 px-4 py-3 bg-primary hover:bg-primary-dark text-white font-semibold rounded-lg shadow-lg hover:shadow-xl transition-all duration-200 transform hover:scale-[1.02]"
                >
                    <span class="material-symbols-outlined">login</span>
                    <span>Iniciar Sesión</span>
                </button>
            </form>
        </div>
        
        <!-- Footer -->
        <p class="text-center text-xs text-gray-500 dark:text-gray-400">
            © 2024 Camet Analytics. Todos los derechos reservados.
        </p>
    </div>
</div>
{% endblock %}
```

## 📦 TASK 7.3: Dashboard Principal y Layout

### Descripción
Crear el layout principal del dashboard con sidebar, header, área de contenido y sistema de navegación. Implementar la estructura base que consumirá los widgets dinámicos.

### Criterios de Aceptación
- Layout responsivo con sidebar colapsable
- Header con información del usuario y acciones
- Sistema de navegación funcional
- Área de contenido preparada para widgets
- Dark mode implementado
- Transiciones suaves entre vistas

### Archivos a Crear

**app/routes/dashboard.py**:
```python
"""
Dashboard routes
"""
from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
from app.wsgi import http_client, async_route, login_required
import httpx

bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@bp.route('/')
@login_required
@async_route
async def index():
    """Dashboard principal"""
    headers = {'Authorization': f"Bearer {session['access_token']}"}
    
    try:
        # Obtener layout del dashboard según rol del usuario
        layout_response = await http_client.get('/api/v1/dashboard/layout', headers=headers)
        layout = layout_response.json() if layout_response.status_code == 200 else {'grid': []}
        
        # Obtener metadatos para filtros
        lines_response = await http_client.get('/api/v1/production/lines', headers=headers)
        products_response = await http_client.get('/api/v1/production/products', headers=headers)
        shifts_response = await http_client.get('/api/v1/production/shifts', headers=headers)
        
        production_lines = lines_response.json() if lines_response.status_code == 200 else []
        products = products_response.json() if products_response.status_code == 200 else []
        shifts = shifts_response.json() if shifts_response.status_code == 200 else []
        
        return render_template(
            'dashboard/index.html',
            layout=layout,
            production_lines=production_lines,
            products=products,
            shifts=shifts
        )
    except httpx.RequestError as e:
        return render_template('errors/500.html', error="Error de conexión con la API"), 500
    except Exception as e:
        return render_template('errors/500.html', error="Error inesperado"), 500

@bp.route('/apply-filters', methods=['POST'])
@login_required
@async_route
async def apply_filters():
    """
    Endpoint HTMX que retorna HTML de widgets actualizados según filtros
    """
    headers = {'Authorization': f"Bearer {session['access_token']}"}
    
    # Obtener filtros del formulario
    filters = {
        'line_id': request.form.get('line_id'),
        'start_date': request.form.get('start_date'),
        'start_time': request.form.get('start_time', '00:00'),
        'end_date': request.form.get('end_date'),
        'end_time': request.form.get('end_time', '23:59'),
        'interval': request.form.get('interval', '15min'),
        'product_ids': request.form.getlist('product_ids'),
        'shift_id': request.form.get('shift_id'),
        'downtime_threshold': request.form.get('downtime_threshold', 5),
        'display_stops': request.form.get('display_stops') == 'on'
    }
    
    # Combinar fecha y hora
    filters['start_date'] = f"{filters['start_date']}T{filters['start_time']}:00"
    filters['end_date'] = f"{filters['end_date']}T{filters['end_time']}:00"
    
    try:
        # Obtener layout
        layout_response = await http_client.get('/api/v1/dashboard/layout', headers=headers)
        layout = layout_response.json() if layout_response.status_code == 200 else {'grid': []}
        
        # Renderizar widgets con los nuevos filtros
        widgets_data = []
        for widget_config in layout.get('grid', []):
            widget_id = widget_config['widget_id']
            
            # Obtener datos del widget desde la API
            widget_response = await http_client.post(
                f'/api/v1/dashboard/widgets/{widget_id}/data',
                headers=headers,
                json=filters,
                timeout=30.0
            )
            
            if widget_response.status_code == 200:
                widget_data = widget_response.json()
                widget_data['config'] = widget_config
                widgets_data.append(widget_data)
        
        return render_template('dashboard/widgets_grid.html', widgets=widgets_data)
        
    except httpx.TimeoutException:
        return '<div class="col-span-full bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-6 text-center"><p class="text-red-600 dark:text-red-400">Timeout: La consulta tardó demasiado tiempo</p></div>', 504
    except Exception as e:
        return '<div class="col-span-full bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-6 text-center"><p class="text-red-600 dark:text-red-400">Error al cargar los datos</p></div>', 500
```

**app/templates/dashboard/index.html**:
```html
{% extends "dashboard/base_dashboard.html" %}

{% block title %}Dashboard - {{ user.username }}{% endblock %}

{% block dashboard_content %}
<div class="space-y-6">
    <!-- Panel de Filtros -->
    <div class="bg-white dark:bg-surface-dark rounded-lg shadow-md">
        {% include "dashboard/filters.html" %}
    </div>
    
    <!-- Widgets Container -->
    <div id="widgets-container" class="min-h-[400px]">
        <!-- Mensaje inicial -->
        <div class="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-12 text-center">
            <svg class="mx-auto h-16 w-16 text-blue-400 dark:text-blue-500 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
            </svg>
            <h3 class="text-xl font-semibold text-gray-900 dark:text-white mb-2">
                Seleccione los filtros para visualizar datos
            </h3>
            <p class="text-sm text-gray-600 dark:text-gray-400">
                Configure los parámetros de consulta arriba y haga clic en "Aplicar Filtros"
            </p>
        </div>
    </div>
</div>
{% endblock %}
```

**app/templates/dashboard/base_dashboard.html**:
```html
{% extends "base.html" %}

{% block body %}
<div class="flex h-screen overflow-hidden" x-data="{ sidebarOpen: true, darkMode: true }" x-init="darkMode = localStorage.getItem('darkMode') === 'true'">
    <!-- Sidebar -->
    <aside 
        x-show="sidebarOpen" 
        x-transition:enter="transition ease-out duration-200"
        x-transition:enter-start="-translate-x-full"
        x-transition:enter-end="translate-x-0"
        x-transition:leave="transition ease-in duration-150"
        x-transition:leave-start="translate-x-0"
        x-transition:leave-end="-translate-x-full"
        class="fixed inset-y-0 left-0 z-50 w-64 bg-white dark:bg-surface-dark border-r border-gray-200 dark:border-gray-700 lg:static lg:translate-x-0 custom-scrollbar overflow-y-auto"
    >
        <!-- Logo -->
        <div class="flex items-center justify-between h-16 px-6 border-b border-gray-200 dark:border-gray-700">
            <div class="flex items-center gap-3">
                <div class="w-10 h-10 bg-primary rounded-lg flex items-center justify-center">
                    <span class="material-symbols-outlined text-white text-xl icon-filled">monitoring</span>
                </div>
                <span class="font-bold text-lg text-gray-900 dark:text-white">Dashboard</span>
            </div>
        </div>
        
        <!-- Navigation -->
        <nav class="p-4 space-y-2">
            <a href="{{ url_for('dashboard.index') }}" class="flex items-center gap-3 px-4 py-3 text-gray-700 dark:text-gray-200 bg-blue-50 dark:bg-blue-900/20 rounded-lg font-medium">
                <span class="material-symbols-outlined">dashboard</span>
                <span>Dashboard</span>
            </a>
            
            <a href="#" class="flex items-center gap-3 px-4 py-3 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors">
                <span class="material-symbols-outlined">analytics</span>
                <span>Reportes</span>
            </a>
            
            <a href="#" class="flex items-center gap-3 px-4 py-3 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors">
                <span class="material-symbols-outlined">history</span>
                <span>Historial</span>
            </a>
            
            {% if user.role == 'admin' %}
            <div class="pt-4 mt-4 border-t border-gray-200 dark:border-gray-700">
                <p class="px-4 text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Administración</p>
                
                <a href="{{ url_for('admin.users') }}" class="flex items-center gap-3 px-4 py-3 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors">
                    <span class="material-symbols-outlined">group</span>
                    <span>Usuarios</span>
                </a>
                
                <a href="{{ url_for('admin.production') }}" class="flex items-center gap-3 px-4 py-3 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors">
                    <span class="material-symbols-outlined">settings</span>
                    <span>Configuración</span>
                </a>
            </div>
            {% endif %}
        </nav>
        
        <!-- User Info -->
        <div class="absolute bottom-0 left-0 right-0 p-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
            <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-full bg-primary flex items-center justify-center">
                    <span class="text-white font-semibold text-sm">{{ user.username[0].upper() }}</span>
                </div>
                <div class="flex-1 min-w-0">
                    <p class="text-sm font-medium text-gray-900 dark:text-white truncate">{{ user.username }}</p>
                    <p class="text-xs text-gray-500 dark:text-gray-400 truncate">{{ user.role }}</p>
                </div>
            </div>
        </div>
    </aside>
    
    <!-- Main Content -->
    <div class="flex-1 flex flex-col overflow-hidden">
        <!-- Header -->
        <header class="h-16 bg-white dark:bg-surface-dark border-b border-gray-200 dark:border-gray-700 flex items-center justify-between px-6">
            <div class="flex items-center gap-4">
                <!-- Mobile menu button -->
                <button @click="sidebarOpen = !sidebarOpen" class="lg:hidden text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white">
                    <span class="material-symbols-outlined">menu</span>
                </button>
                
                <h1 class="text-xl font-semibold text-gray-900 dark:text-white">
                    {% block page_title %}Dashboard de Producción{% endblock %}
                </h1>
            </div>
            
            <div class="flex items-center gap-3">
                <!-- Dark Mode Toggle -->
                <button 
                    @click="darkMode = !darkMode; localStorage.setItem('darkMode', darkMode); document.documentElement.classList.toggle('dark', darkMode)"
                    class="p-2 rounded-lg text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                >
                    <span class="material-symbols-outlined" x-show="!darkMode">dark_mode</span>
                    <span class="material-symbols-outlined" x-show="darkMode">light_mode</span>
                </button>
                
                <!-- Notifications -->
                <button class="p-2 rounded-lg text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors relative">
                    <span class="material-symbols-outlined">notifications</span>
                    <span class="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full"></span>
                </button>
                
                <!-- User Menu -->
                <div x-data="{ open: false }" class="relative">
                    <button @click="open = !open" class="flex items-center gap-2 px-3 py-2 rounded-lg text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
                        <div class="w-8 h-8 rounded-full bg-primary flex items-center justify-center">
                            <span class="text-white font-semibold text-xs">{{ user.username[0].upper() }}</span>
                        </div>
                        <span class="material-symbols-outlined text-sm">expand_more</span>
                    </button>
                    
                    <!-- Dropdown -->
                    <div 
                        x-show="open" 
                        @click.away="open = false"
                        x-transition:enter="transition ease-out duration-100"
                        x-transition:enter-start="transform opacity-0 scale-95"
                        x-transition:enter-end="transform opacity-100 scale-100"
                        x-transition:leave="transition ease-in duration-75"
                        x-transition:leave-start="transform opacity-100 scale-100"
                        x-transition:leave-end="transform opacity-0 scale-95"
                        class="absolute right-0 mt-2 w-48 bg-white dark:bg-surface-dark rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 py-1 z-50"
                    >
                        <a href="#" class="flex items-center gap-2 px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800">
                            <span class="material-symbols-outlined text-[18px]">person</span>
                            <span>Mi Perfil</span>
                        </a>
                        <a href="#" class="flex items-center gap-2 px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800">
                            <span class="material-symbols-outlined text-[18px]">settings</span>
                            <span>Configuración</span>
                        </a>
                        <hr class="my-1 border-gray-200 dark:border-gray-700">
                        <a href="{{ url_for('auth.logout') }}" class="flex items-center gap-2 px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20">
                            <span class="material-symbols-outlined text-[18px]">logout</span>
                            <span>Cerrar Sesión</span>
                        </a>
                    </div>
                </div>
            </div>
        </header>
        
        <!-- Page Content -->
        <main class="flex-1 overflow-y-auto bg-gray-50 dark:bg-background-dark p-6 custom-scrollbar">
            {% block dashboard_content %}{% endblock %}
        </main>
    </div>
</div>

<!-- Loading Overlay -->
<div id="loading-overlay" class="htmx-indicator fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
    <div class="bg-white dark:bg-surface-dark rounded-lg p-6 shadow-xl">
        <div class="flex items-center gap-4">
            <span class="material-symbols-outlined animate-spin text-primary text-3xl">progress_activity</span>
            <span class="text-lg font-medium text-gray-900 dark:text-white">Cargando datos...</span>
        </div>
    </div>
</div>
{% endblock %}
```

**app/templates/errors/404.html**:
```html
{% extends "base.html" %}

{% block title %}Página no encontrada - 404{% endblock %}

{% block body %}
<div class="min-h-screen flex items-center justify-center px-4 bg-gray-50 dark:bg-background-dark">
    <div class="max-w-md w-full text-center">
        <div class="mb-8">
            <span class="material-symbols-outlined text-9xl text-gray-300 dark:text-gray-700">error_outline</span>
        </div>
        <h1 class="text-4xl font-bold text-gray-900 dark:text-white mb-4">404</h1>
        <p class="text-xl text-gray-600 dark:text-gray-400 mb-8">Página no encontrada</p>
        <a href="{{ url_for('dashboard.index') if user else url_for('auth.login') }}" class="inline-flex items-center gap-2 px-6 py-3 bg-primary text-white rounded-lg hover:bg-primary-dark transition-colors">
            <span class="material-symbols-outlined">home</span>
            <span>Volver al inicio</span>
        </a>
    </div>
</div>
{% endblock %}
```

**app/templates/errors/500.html**:
```html
{% extends "base.html" %}

{% block title %}Error del servidor - 500{% endblock %}

{% block body %}
<div class="min-h-screen flex items-center justify-center px-4 bg-gray-50 dark:bg-background-dark">
    <div class="max-w-md w-full text-center">
        <div class="mb-8">
            <span class="material-symbols-outlined text-9xl text-red-300 dark:text-red-700">report</span>
        </div>
        <h1 class="text-4xl font-bold text-gray-900 dark:text-white mb-4">500</h1>
        <p class="text-xl text-gray-600 dark:text-gray-400 mb-4">Error interno del servidor</p>
        {% if error %}
        <p class="text-sm text-gray-500 dark:text-gray-500 mb-8">{{ error }}</p>
        {% endif %}
        <a href="{{ url_for('dashboard.index') if user else url_for('auth.login') }}" class="inline-flex items-center gap-2 px-6 py-3 bg-primary text-white rounded-lg hover:bg-primary-dark transition-colors">
            <span class="material-symbols-outlined">refresh</span>
            <span>Intentar nuevamente</span>
        </a>
    </div>
</div>
{% endblock %}
```

**app/templates/errors/403.html**:
```html
{% extends "base.html" %}

{% block title %}Acceso denegado - 403{% endblock %}

{% block body %}
<div class="min-h-screen flex items-center justify-center px-4 bg-gray-50 dark:bg-background-dark">
    <div class="max-w-md w-full text-center">
        <div class="mb-8">
            <span class="material-symbols-outlined text-9xl text-yellow-300 dark:text-yellow-700">block</span>
        </div>
        <h1 class="text-4xl font-bold text-gray-900 dark:text-white mb-4">403</h1>
        <p class="text-xl text-gray-600 dark:text-gray-400 mb-8">No tiene permisos para acceder a este recurso</p>
        <a href="{{ url_for('dashboard.index') }}" class="inline-flex items-center gap-2 px-6 py-3 bg-primary text-white rounded-lg hover:bg-primary-dark transition-colors">
            <span class="material-symbols-outlined">arrow_back</span>
            <span>Volver al dashboard</span>
        </a>
    </div>
</div>
{% endblock %}
```

**app/routes/admin.py** (placeholder para rutas admin):
```python
"""
Admin routes (placeholder)
"""
from flask import Blueprint, render_template
from app.wsgi import login_required

bp = Blueprint('admin', __name__, url_prefix='/admin')

@bp.route('/users')
@login_required
def users():
    return render_template('admin/users.html')

@bp.route('/production')
@login_required
def production():
    return render_template('admin/production.html')
```

### Verificación
```bash
# 1. Reiniciar Flask
python app/wsgi.py

# 2. Navegar a http://localhost:5000

# 3. Login con credenciales de prueba

# 4. Verificar:
# - Sidebar responsive
# - Dark mode toggle funcional
# - User menu con dropdown
# - Navegación entre secciones
# - Error pages (404, 500, 403)
```
## 📦 TASK 7.4: Panel de Filtros con HTMX y Alpine.js

### Descripción
Crear el panel de filtros dinámico que permite al usuario seleccionar parámetros de consulta (línea, fechas, productos, turnos, intervalo) y que use HTMX para enviar requests al backend sin recargar la página.

### Criterios de Aceptación
- Panel de filtros con todos los campos necesarios
- Validación de fechas en frontend
- Presets de fechas rápidos (hoy, ayer, últimos 7 días)
- HTMX para enviar filtros sin reload
- Alpine.js para lógica reactiva del formulario
- Loading indicator durante requests
- Botón de reset funcional

### Archivos a Crear

**app/templates/dashboard/filters.html**:
```html
<div class="p-6" x-data="filterPanel()" x-init="init()">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
        <h3 class="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <span class="material-symbols-outlined text-primary">tune</span>
            Filtros de Consulta
        </h3>
        <button
            @click="resetFilters()"
            class="text-xs text-text-sub hover:text-primary transition-colors flex items-center gap-1"
        >
            <span class="material-symbols-outlined text-[16px]">restart_alt</span>
            Restablecer
        </button>
    </div>
    
    <!-- Formulario -->
    <form
        hx-post="{{ url_for('dashboard.apply_filters') }}"
        hx-target="#widgets-container"
        hx-swap="innerHTML"
        hx-indicator="#loading-overlay"
        class="space-y-6"
    >
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
        
        <!-- Fila 1: Filtros Básicos -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <!-- Línea de Producción -->
            <div>
                <label class="block text-xs font-bold text-text-sub uppercase tracking-wide mb-2">
                    Línea de Producción *
                </label>
                <div class="relative">
                    <select
                        name="line_id"
                        required
                        x-model="filters.line_id"
                        class="w-full appearance-none px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-md bg-gray-50 dark:bg-gray-800 text-text-main dark:text-white focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent text-sm"
                    >
                        <option value="">Seleccione una línea</option>
                        {% for line in production_lines %}
                        <option value="{{ line.line_id }}">{{ line.line_name }}</option>
                        {% endfor %}
                    </select>
                    <span class="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-text-sub pointer-events-none text-[20px]">
                        expand_more
                    </span>
                </div>
            </div>
            
            <!-- Producto -->
            <div>
                <label class="block text-xs font-bold text-text-sub uppercase tracking-wide mb-2">
                    Producto
                </label>
                <div class="relative">
                    <select
                        name="product_ids"
                        x-model="filters.product_ids"
                        multiple
                        size="1"
                        class="w-full appearance-none px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-md bg-gray-50 dark:bg-gray-800 text-text-main dark:text-white focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent text-sm"
                    >
                        <option value="">Todos los productos</option>
                        {% for product in products %}
                        <option value="{{ product.product_id }}">{{ product.product_name }}</option>
                        {% endfor %}
                    </select>
                    <span class="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-text-sub pointer-events-none text-[20px]">
                        expand_more
                    </span>
                </div>
                <p class="text-xs text-text-sub mt-1">Mantener Ctrl para seleccionar múltiples</p>
            </div>
            
            <!-- Intervalo de Agregación -->
            <div>
                <label class="block text-xs font-bold text-text-sub uppercase tracking-wide mb-2">
                    Intervalo de Agregación
                </label>
                <div class="relative">
                    <select
                        name="interval"
                        x-model="filters.interval"
                        class="w-full appearance-none px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-md bg-gray-50 dark:bg-gray-800 text-text-main dark:text-white focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent text-sm"
                    >
                        <option value="1min">1 Minuto</option>
                        <option value="15min" selected>15 Minutos</option>
                        <option value="1hour">1 Hora</option>
                        <option value="1day">1 Día</option>
                        <option value="1week">1 Semana</option>
                        <option value="1month">1 Mes</option>
                    </select>
                    <span class="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-text-sub pointer-events-none text-[20px]">
                        expand_more
                    </span>
                </div>
            </div>
        </div>
        
        <!-- Divider -->
        <div class="border-t border-gray-200 dark:border-gray-700"></div>
        
        <!-- Fila 2: Filtros de Fecha y Hora -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <!-- Fecha de Inicio -->
            <div>
                <label class="block text-xs font-bold text-text-sub uppercase tracking-wide mb-2">
                    Fecha de Inicio *
                </label>
                <div class="relative">
                    <input
                        type="date"
                        name="start_date"
                        required
                        x-model="filters.start_date"
                        class="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-md bg-gray-50 dark:bg-gray-800 text-text-main dark:text-white focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent text-sm"
                    />
                    <span class="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-text-sub pointer-events-none text-[20px]">
                        calendar_today
                    </span>
                </div>
            </div>
            
            <!-- Hora de Inicio -->
            <div>
                <label class="block text-xs font-bold text-text-sub uppercase tracking-wide mb-2">
                    Hora de Inicio *
                </label>
                <div class="relative">
                    <input
                        type="time"
                        name="start_time"
                        required
                        x-model="filters.start_time"
                        class="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-md bg-gray-50 dark:bg-gray-800 text-text-main dark:text-white focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent text-sm"
                    />
                    <span class="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-text-sub pointer-events-none text-[20px]">
                        schedule
                    </span>
                </div>
            </div>
            
            <!-- Fecha de Fin -->
            <div>
                <label class="block text-xs font-bold text-text-sub uppercase tracking-wide mb-2">
                    Fecha de Fin *
                </label>
                <div class="relative">
                    <input
                        type="date"
                        name="end_date"
                        required
                        x-model="filters.end_date"
                        class="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-md bg-gray-50 dark:bg-gray-800 text-text-main dark:text-white focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent text-sm"
                    />
                    <span class="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-text-sub pointer-events-none text-[20px]">
                        calendar_today
                    </span>
                </div>
            </div>
            
            <!-- Hora de Fin -->
            <div>
                <label class="block text-xs font-bold text-text-sub uppercase tracking-wide mb-2">
                    Hora de Fin *
                </label>
                <div class="relative">
                    <input
                        type="time"
                        name="end_time"
                        required
                        x-model="filters.end_time"
                        class="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-md bg-gray-50 dark:bg-gray-800 text-text-main dark:text-white focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent text-sm"
                    />
                    <span class="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-text-sub pointer-events-none text-[20px]">
                        schedule
                    </span>
                </div>
            </div>
        </div>
        
        <!-- Fila 3: Filtros Adicionales -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            <!-- Turno -->
            <div>
                <label class="block text-xs font-bold text-text-sub uppercase tracking-wide mb-2">
                    Turno
                </label>
                <div class="relative">
                    <select
                        name="shift_id"
                        x-model="filters.shift_id"
                        class="w-full appearance-none px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-md bg-gray-50 dark:bg-gray-800 text-text-main dark:text-white focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent text-sm"
                    >
                        <option value="">Todos los turnos</option>
                        {% for shift in shifts %}
                        <option value="{{ shift.shift_id }}">{{ shift.shift_name }}</option>
                        {% endfor %}
                    </select>
                    <span class="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-text-sub pointer-events-none text-[20px]">
                        expand_more
                    </span>
                </div>
            </div>
            
            <!-- Umbral de Parada -->
            <div>
                <label class="block text-xs font-bold text-text-sub uppercase tracking-wide mb-2">
                    Umbral de Parada (min)
                </label>
                <div class="relative">
                    <input
                        type="number"
                        name="downtime_threshold"
                        x-model="filters.downtime_threshold"
                        min="1"
                        max="60"
                        value="5"
                        class="w-full px-3 py-2 pr-12 border border-gray-300 dark:border-gray-700 rounded-md bg-gray-50 dark:bg-gray-800 text-text-main dark:text-white focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent text-sm"
                    />
                    <span class="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-text-sub font-bold">
                        MIN
                    </span>
                </div>
            </div>
            
            <!-- Mostrar Paradas -->
            <div class="flex items-end">
                <label class="flex items-center gap-2 cursor-pointer group">
                    <input
                        type="checkbox"
                        name="display_stops"
                        x-model="filters.display_stops"
                        class="w-4 h-4 rounded border-gray-300 text-primary focus:ring-primary"
                    />
                    <span class="text-sm font-medium text-text-main dark:text-white group-hover:text-primary transition-colors">
                        Mostrar Paradas
                    </span>
                </label>
            </div>
        </div>
        
        <!-- Acciones -->
        <div class="flex items-center justify-between pt-4 border-t border-gray-200 dark:border-gray-700">
            <!-- Presets Rápidos -->
            <div class="flex gap-2">
                <button
                    type="button"
                    @click="applyPreset('today')"
                    class="px-3 py-1.5 text-xs font-medium text-text-sub hover:text-primary hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md transition-colors"
                >
                    Hoy
                </button>
                <button
                    type="button"
                    @click="applyPreset('yesterday')"
                    class="px-3 py-1.5 text-xs font-medium text-text-sub hover:text-primary hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md transition-colors"
                >
                    Ayer
                </button>
                <button
                    type="button"
                    @click="applyPreset('last7days')"
                    class="px-3 py-1.5 text-xs font-medium text-text-sub hover:text-primary hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md transition-colors"
                >
                    Últimos 7 días
                </button>
                <button
                    type="button"
                    @click="applyPreset('lastMonth')"
                    class="px-3 py-1.5 text-xs font-medium text-text-sub hover:text-primary hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md transition-colors"
                >
                    Último mes
                </button>
            </div>
            
            <!-- Botones de Acción -->
            <div class="flex gap-3">
                <button
                    type="button"
                    @click="exportData()"
                    class="px-4 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-text-main dark:text-white text-sm font-medium rounded-md hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center gap-2 transition-colors"
                >
                    <span class="material-symbols-outlined text-[18px]">file_download</span>
                    Exportar
                </button>
                
                <button
                    type="submit"
                    class="px-6 py-2 bg-primary text-white text-sm font-bold uppercase rounded-md hover:bg-primary-dark flex items-center gap-2 shadow-sm shadow-blue-200 dark:shadow-none transition-all"
                >
                    <span class="material-symbols-outlined text-[18px]">search</span>
                    Aplicar Filtros
                </button>
            </div>
        </div>
    </form>
</div>

<!-- Alpine.js Logic -->
<script>
function filterPanel() {
    return {
        filters: {
            line_id: '',
            product_ids: [],
            interval: '15min',
            start_date: '',
            start_time: '00:00',
            end_date: '',
            end_time: '23:59',
            shift_id: '',
            downtime_threshold: 5,
            display_stops: true
        },
        
        init() {
            // Set default date range (today)
            this.applyPreset('today');
        },
        
        formatDate(date) {
            const year = date.getFullYear();
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            return `${year}-${month}-${day}`;
        },
        
        applyPreset(preset) {
            const now = new Date();
            const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
            
            switch(preset) {
                case 'today':
                    this.filters.start_date = this.formatDate(today);
                    this.filters.end_date = this.formatDate(today);
                    this.filters.start_time = '00:00';
                    this.filters.end_time = '23:59';
                    break;
                    
                case 'yesterday':
                    const yesterday = new Date(today);
                    yesterday.setDate(yesterday.getDate() - 1);
                    this.filters.start_date = this.formatDate(yesterday);
                    this.filters.end_date = this.formatDate(yesterday);
                    this.filters.start_time = '00:00';
                    this.filters.end_time = '23:59';
                    break;
                    
                case 'last7days':
                    const weekAgo = new Date(today);
                    weekAgo.setDate(weekAgo.getDate() - 7);
                    this.filters.start_date = this.formatDate(weekAgo);
                    this.filters.end_date = this.formatDate(today);
                    this.filters.start_time = '00:00';
                    this.filters.end_time = '23:59';
                    break;
                    
                case 'lastMonth':
                    const monthAgo = new Date(today);
                    monthAgo.setDate(monthAgo.getDate() - 30);
                    this.filters.start_date = this.formatDate(monthAgo);
                    this.filters.end_date = this.formatDate(today);
                    this.filters.start_time = '00:00';
                    this.filters.end_time = '23:59';
                    break;
            }
        },
        
        resetFilters() {
            this.filters = {
                line_id: '',
                product_ids: [],
                interval: '15min',
                start_date: '',
                start_time: '00:00',
                end_date: '',
                end_time: '23:59',
                shift_id: '',
                downtime_threshold: 5,
                display_stops: true
            };
            this.applyPreset('today');
            
            // Clear widgets container
            document.getElementById('widgets-container').innerHTML = `
                <div class="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-12 text-center">
                    <svg class="mx-auto h-16 w-16 text-blue-400 dark:text-blue-500 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
                    </svg>
                    <h3 class="text-xl font-semibold text-gray-900 dark:text-white mb-2">
                        Seleccione los filtros para visualizar datos
                    </h3>
                    <p class="text-sm text-gray-600 dark:text-gray-400">
                        Configure los parámetros de consulta arriba y haga clic en "Aplicar Filtros"
                    </p>
                </div>
            `;
        },
        
        exportData() {
            // Validar que hay una línea seleccionada
            if (!this.filters.line_id) {
                showToast('Por favor seleccione una línea de producción', 'warning');
                return;
            }
            
            // Mostrar mensaje de funcionalidad futura
            showToast('Funcionalidad de exportación en desarrollo', 'info');
            
            // TODO: Implementar exportación a Excel/CSV
            // const params = new URLSearchParams(this.filters);
            // window.location.href = `/dashboard/export?${params}`;
        }
    }
}
</script>
```

### Verificación
```bash
# 1. Reiniciar Flask
python app/wsgi.py

# 2. Login y navegar al dashboard

# 3. Verificar funcionalidad del panel de filtros:
# - Presets de fechas (hoy, ayer, últimos 7 días)
# - Selección de línea (requerido)
# - Selección múltiple de productos
# - Cambio de intervalo
# - Validación de campos requeridos
# - Botón reset limpia campos
# - Submit envía request HTMX sin reload
```

---

## 📦 TASK 7.5: Grid de Widgets Dinámicos

### Descripción
Crear el sistema de renderizado de widgets que muestra los componentes según el layout configurado en DASHBOARD_TEMPLATE. El grid debe ser responsivo y adaptar el tamaño de los widgets automáticamente.

### Criterios de Aceptación
- Grid responsivo con Tailwind CSS
- Widgets se renderizan según configuración del backend
- Cada widget tiene su propio template
- Grid se actualiza vía HTMX sin reload
- Loading states para cada widget
- Manejo de errores por widget individual

### Archivos a Crear

**app/templates/dashboard/widgets_grid.html**:
```html
{% if widgets %}
<div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6 fade-in">
    {% for widget in widgets %}
    <div class="
        {% if widget.config.w >= 8 %}col-span-full
        {% elif widget.config.w >= 6 %}md:col-span-2
        {% elif widget.config.w >= 4 %}md:col-span-1 xl:col-span-2
        {% else %}md:col-span-1{% endif %}
        {% if widget.config.h >= 6 %}row-span-2{% endif %}
    ">
        {% if widget.widget_type == 'line_chart' %}
            {% include 'dashboard/widgets/line_chart.html' %}
        {% elif widget.widget_type == 'pie_chart' %}
            {% include 'dashboard/widgets/pie_chart.html' %}
        {% elif widget.widget_type == 'bar_chart' %}
            {% include 'dashboard/widgets/bar_chart.html' %}
        {% elif widget.widget_type == 'kpi_card' %}
            {% include 'dashboard/widgets/kpi_card.html' %}
        {% elif widget.widget_type == 'table' %}
            {% include 'dashboard/widgets/table.html' %}
        {% elif widget.widget_type == 'comparison_bar' %}
            {% include 'dashboard/widgets/comparison_bar.html' %}
        {% else %}
            {% include 'dashboard/widgets/unknown.html' %}
        {% endif %}
    </div>
    {% endfor %}
</div>
{% else %}
<div class="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-8 text-center">
    <span class="material-symbols-outlined text-6xl text-yellow-400 dark:text-yellow-500 mb-4">warning</span>
    <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-2">
        No se encontraron datos
    </h3>
    <p class="text-sm text-gray-600 dark:text-gray-400">
        No hay datos disponibles para los filtros seleccionados. Intente con un rango de fechas diferente.
    </p>
</div>
{% endif %}
```

**app/templates/dashboard/widgets/unknown.html**:
```html
<div class="bg-white dark:bg-surface-dark rounded-lg shadow-md p-6 border-2 border-dashed border-gray-300 dark:border-gray-600">
    <div class="text-center">
        <span class="material-symbols-outlined text-6xl text-gray-300 dark:text-gray-600 mb-4">extension</span>
        <p class="text-sm text-gray-600 dark:text-gray-400">
            Widget tipo "{{ widget.widget_type }}" no implementado
        </p>
    </div>
</div>
```

### Verificación
```bash
# 1. Aplicar filtros en el dashboard
# 2. Verificar que el grid se renderiza correctamente
# 3. Verificar responsive design (mobile, tablet, desktop)
# 4. Verificar que widgets desconocidos muestran placeholder
```

## 📦 TASK 7.6: Implementación de Widgets Individuales

### Descripción
Crear los templates individuales para cada tipo de widget: Line Chart, Pie Chart, Bar Chart, KPI Cards y Tables. Cada widget debe renderizar datos con Chart.js y tener un diseño consistente.

### Criterios de Aceptación
- Cada widget tiene su propio template
- Chart.js configurado correctamente para cada tipo
- Diseño consistente entre widgets
- Animaciones suaves
- Responsive design
- Dark mode compatible
- Manejo de datos vacíos

### Archivos a Crear

**app/templates/dashboard/widgets/line_chart.html**:
```html
<div class="bg-white dark:bg-surface-dark rounded-lg shadow-md p-6 h-full flex flex-col">
    <!-- Header -->
    <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <span class="material-symbols-outlined text-primary">show_chart</span>
            {{ widget.widget_name }}
        </h3>
        <button class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors">
            <span class="material-symbols-outlined text-[20px]">more_vert</span>
        </button>
    </div>
    
    <!-- Chart Container -->
    {% if widget.data and widget.data.labels %}
    <div class="flex-1 relative min-h-[300px]">
        <canvas id="chart-{{ widget.widget_id }}-{{ loop.index }}"></canvas>
    </div>
    
    <script>
    (function() {
        const ctx = document.getElementById('chart-{{ widget.widget_id }}-{{ loop.index }}');
        if (!ctx) return;
        
        const isDark = document.documentElement.classList.contains('dark');
        const textColor = isDark ? '#e5e7eb' : '#374151';
        const gridColor = isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';
        
        new Chart(ctx, {
            type: 'line',
            data: {{ widget.data | tojson }},
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                plugins: {
                    legend: {
                        position: 'top',
                        labels: {
                            color: textColor,
                            padding: 15,
                            font: {
                                size: 12,
                                family: 'Inter'
                            }
                        }
                    },
                    tooltip: {
                        backgroundColor: isDark ? '#1e293b' : '#ffffff',
                        titleColor: textColor,
                        bodyColor: textColor,
                        borderColor: isDark ? '#475569' : '#e5e7eb',
                        borderWidth: 1,
                        padding: 12,
                        displayColors: true,
                        callbacks: {
                            label: function(context) {
                                let label = context.dataset.label || '';
                                if (label) {
                                    label += ': ';
                                }
                                if (context.parsed.y !== null) {
                                    label += context.parsed.y.toLocaleString();
                                }
                                return label;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: {
                            color: gridColor,
                            drawBorder: false
                        },
                        ticks: {
                            color: textColor,
                            font: {
                                size: 11,
                                family: 'Inter'
                            },
                            maxRotation: 45,
                            minRotation: 0
                        }
                    },
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: gridColor,
                            drawBorder: false
                        },
                        ticks: {
                            color: textColor,
                            font: {
                                size: 11,
                                family: 'Inter'
                            },
                            precision: 0,
                            callback: function(value) {
                                return value.toLocaleString();
                            }
                        }
                    }
                }
            }
        });
    })();
    </script>
    {% else %}
    <div class="flex-1 flex items-center justify-center">
        <div class="text-center">
            <span class="material-symbols-outlined text-6xl text-gray-300 dark:text-gray-600 mb-2">bar_chart</span>
            <p class="text-sm text-gray-500 dark:text-gray-400">No hay datos disponibles</p>
        </div>
    </div>
    {% endif %}
</div>
```

**app/templates/dashboard/widgets/pie_chart.html**:
```html
<div class="bg-white dark:bg-surface-dark rounded-lg shadow-md p-6 h-full flex flex-col">
    <!-- Header -->
    <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <span class="material-symbols-outlined text-primary">pie_chart</span>
            {{ widget.widget_name }}
        </h3>
        <button class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors">
            <span class="material-symbols-outlined text-[20px]">more_vert</span>
        </button>
    </div>
    
    <!-- Chart Container -->
    {% if widget.data and widget.data.labels %}
    <div class="flex-1 relative min-h-[300px] flex items-center justify-center">
        <canvas id="pie-chart-{{ widget.widget_id }}-{{ loop.index }}"></canvas>
    </div>
    
    <script>
    (function() {
        const ctx = document.getElementById('pie-chart-{{ widget.widget_id }}-{{ loop.index }}');
        if (!ctx) return;
        
        const isDark = document.documentElement.classList.contains('dark');
        const textColor = isDark ? '#e5e7eb' : '#374151';
        
        new Chart(ctx, {
            type: 'pie',
            data: {{ widget.data | tojson }},
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right',
                        labels: {
                            color: textColor,
                            padding: 15,
                            font: {
                                size: 12,
                                family: 'Inter'
                            },
                            generateLabels: function(chart) {
                                const data = chart.data;
                                if (data.labels.length && data.datasets.length) {
                                    return data.labels.map((label, i) => {
                                        const value = data.datasets[0].data[i];
                                        const total = data.datasets[0].data.reduce((a, b) => a + b, 0);
                                        const percentage = ((value / total) * 100).toFixed(1);
                                        return {
                                            text: `${label}: ${percentage}%`,
                                            fillStyle: data.datasets[0].backgroundColor[i],
                                            hidden: false,
                                            index: i
                                        };
                                    });
                                }
                                return [];
                            }
                        }
                    },
                    tooltip: {
                        backgroundColor: isDark ? '#1e293b' : '#ffffff',
                        titleColor: textColor,
                        bodyColor: textColor,
                        borderColor: isDark ? '#475569' : '#e5e7eb',
                        borderWidth: 1,
                        padding: 12,
                        callbacks: {
                            label: function(context) {
                                const label = context.label || '';
                                const value = context.parsed;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((value / total) * 100).toFixed(1);
                                return `${label}: ${value.toLocaleString()} (${percentage}%)`;
                            }
                        }
                    }
                }
            }
        });
    })();
    </script>
    {% else %}
    <div class="flex-1 flex items-center justify-center">
        <div class="text-center">
            <span class="material-symbols-outlined text-6xl text-gray-300 dark:text-gray-600 mb-2">pie_chart</span>
            <p class="text-sm text-gray-500 dark:text-gray-400">No hay datos disponibles</p>
        </div>
    </div>
    {% endif %}
</div>
```

**app/templates/dashboard/widgets/bar_chart.html**:
```html
<div class="bg-white dark:bg-surface-dark rounded-lg shadow-md p-6 h-full flex flex-col">
    <!-- Header -->
    <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <span class="material-symbols-outlined text-primary">bar_chart</span>
            {{ widget.widget_name }}
        </h3>
        <button class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors">
            <span class="material-symbols-outlined text-[20px]">more_vert</span>
        </button>
    </div>
    
    <!-- Chart Container -->
    {% if widget.data and widget.data.labels %}
    <div class="flex-1 relative min-h-[300px]">
        <canvas id="bar-chart-{{ widget.widget_id }}-{{ loop.index }}"></canvas>
    </div>
    
    <script>
    (function() {
        const ctx = document.getElementById('bar-chart-{{ widget.widget_id }}-{{ loop.index }}');
        if (!ctx) return;
        
        const isDark = document.documentElement.classList.contains('dark');
        const textColor = isDark ? '#e5e7eb' : '#374151';
        const gridColor = isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';
        
        new Chart(ctx, {
            type: 'bar',
            data: {{ widget.data | tojson }},
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: isDark ? '#1e293b' : '#ffffff',
                        titleColor: textColor,
                        bodyColor: textColor,
                        borderColor: isDark ? '#475569' : '#e5e7eb',
                        borderWidth: 1,
                        padding: 12,
                        callbacks: {
                            label: function(context) {
                                return `${context.label}: ${context.parsed.y.toLocaleString()} unidades`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            color: textColor,
                            font: {
                                size: 12,
                                family: 'Inter',
                                weight: '500'
                            }
                        }
                    },
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: gridColor,
                            drawBorder: false
                        },
                        ticks: {
                            color: textColor,
                            font: {
                                size: 11,
                                family: 'Inter'
                            },
                            precision: 0,
                            callback: function(value) {
                                return value.toLocaleString();
                            }
                        }
                    }
                }
            }
        });
    })();
    </script>
    {% else %}
    <div class="flex-1 flex items-center justify-center">
        <div class="text-center">
            <span class="material-symbols-outlined text-6xl text-gray-300 dark:text-gray-600 mb-2">bar_chart</span>
            <p class="text-sm text-gray-500 dark:text-gray-400">No hay datos disponibles</p>
        </div>
    </div>
    {% endif %}
</div>
```

**app/templates/dashboard/widgets/kpi_card.html**:
```html
<div class="bg-white dark:bg-surface-dark rounded-lg shadow-md p-6 h-full">
    <div class="flex items-center justify-between h-full">
        <div class="flex-1">
            <p class="text-sm font-medium text-gray-600 dark:text-gray-400 mb-2">
                {{ widget.data.label if widget.data else widget.widget_name }}
            </p>
            
            {% if widget.data %}
            <div class="flex items-baseline gap-2">
                <p class="text-4xl font-bold text-gray-900 dark:text-white">
                    {{ widget.data.value }}
                </p>
                <span class="text-lg font-normal text-gray-600 dark:text-gray-400">
                    {{ widget.data.unit }}
                </span>
            </div>
            
            <!-- Trend Indicator (opcional) -->
            {% if widget.data.trend %}
            <div class="mt-3 flex items-center gap-1">
                {% if widget.data.trend > 0 %}
                <span class="material-symbols-outlined text-green-500 text-[18px]">trending_up</span>
                <span class="text-sm text-green-600 dark:text-green-400 font-medium">+{{ widget.data.trend }}%</span>
                {% elif widget.data.trend < 0 %}
                <span class="material-symbols-outlined text-red-500 text-[18px]">trending_down</span>
                <span class="text-sm text-red-600 dark:text-red-400 font-medium">{{ widget.data.trend }}%</span>
                {% else %}
                <span class="material-symbols-outlined text-gray-500 text-[18px]">trending_flat</span>
                <span class="text-sm text-gray-600 dark:text-gray-400 font-medium">Sin cambios</span>
                {% endif %}
                <span class="text-xs text-gray-500 dark:text-gray-500 ml-1">vs período anterior</span>
            </div>
            {% endif %}
            {% else %}
            <p class="text-2xl font-bold text-gray-400 dark:text-gray-600">--</p>
            <p class="text-xs text-gray-500 dark:text-gray-500 mt-2">No hay datos</p>
            {% endif %}
        </div>
        
        <!-- Icon -->
        <div class="flex-shrink-0 ml-4">
            {% if widget.data %}
                {% if 'oee' in widget.data.label.lower() %}
                <div class="w-16 h-16 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center">
                    <span class="material-symbols-outlined text-blue-600 dark:text-blue-400 text-3xl icon-filled">monitoring</span>
                </div>
                {% elif 'production' in widget.data.label.lower() or 'producción' in widget.data.label.lower() %}
                <div class="w-16 h-16 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center">
                    <span class="material-symbols-outlined text-green-600 dark:text-green-400 text-3xl icon-filled">inventory_2</span>
                </div>
                {% elif 'weight' in widget.data.label.lower() or 'peso' in widget.data.label.lower() %}
                <div class="w-16 h-16 bg-purple-100 dark:bg-purple-900/30 rounded-full flex items-center justify-center">
                    <span class="material-symbols-outlined text-purple-600 dark:text-purple-400 text-3xl icon-filled">scale</span>
                </div>
                {% elif 'downtime' in widget.data.label.lower() or 'parada' in widget.data.label.lower() %}
                <div class="w-16 h-16 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center">
                    <span class="material-symbols-outlined text-red-600 dark:text-red-400 text-3xl icon-filled">warning</span>
                </div>
                {% else %}
                <div class="w-16 h-16 bg-gray-100 dark:bg-gray-800 rounded-full flex items-center justify-center">
                    <span class="material-symbols-outlined text-gray-600 dark:text-gray-400 text-3xl icon-filled">analytics</span>
                </div>
                {% endif %}
            {% else %}
            <div class="w-16 h-16 bg-gray-100 dark:bg-gray-800 rounded-full flex items-center justify-center">
                <span class="material-symbols-outlined text-gray-400 dark:text-gray-600 text-3xl">help_outline</span>
            </div>
            {% endif %}
        </div>
    </div>
</div>
```

**app/templates/dashboard/widgets/table.html**:
```html
<div class="bg-white dark:bg-surface-dark rounded-lg shadow-md overflow-hidden">
    <!-- Header -->
    <div class="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
        <h3 class="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <span class="material-symbols-outlined text-primary">table_chart</span>
            {{ widget.widget_name }}
        </h3>
        <div class="flex items-center gap-2">
            <button class="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors rounded hover:bg-gray-100 dark:hover:bg-gray-800">
                <span class="material-symbols-outlined text-[20px]">file_download</span>
            </button>
            <button class="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors rounded hover:bg-gray-100 dark:hover:bg-gray-800">
                <span class="material-symbols-outlined text-[20px]">more_vert</span>
            </button>
        </div>
    </div>
    
    <!-- Table -->
    {% if widget.data and widget.data.rows %}
    <div class="overflow-x-auto custom-scrollbar">
        <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
            <thead class="bg-gray-50 dark:bg-gray-800/50">
                <tr>
                    {% for column in widget.data.columns %}
                    <th scope="col" class="px-6 py-3 text-left text-xs font-bold text-gray-600 dark:text-gray-400 uppercase tracking-wider">
                        {{ column }}
                    </th>
                    {% endfor %}
                </tr>
            </thead>
            <tbody class="bg-white dark:bg-surface-dark divide-y divide-gray-200 dark:divide-gray-700">
                {% for row in widget.data.rows %}
                <tr class="hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-white">
                        {{ row.start_time }}
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-white">
                        {{ row.end_time }}
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">
                        <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-400">
                            {{ row.duration }}
                        </span>
                    </td>
                    <td class="px-6 py-4 text-sm text-gray-600 dark:text-gray-400">
                        {{ row.reason if row.reason else 'Sin especificar' }}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    
    <!-- Pagination (si hay muchos registros) -->
    {% if widget.data.rows|length > 10 %}
    <div class="px-6 py-4 border-t border-gray-200 dark:border-gray-700 flex items-center justify-between">
        <p class="text-sm text-gray-600 dark:text-gray-400">
            Mostrando <span class="font-medium">{{ widget.data.rows|length }}</span> registros
        </p>
        <div class="flex gap-2">
            <button class="px-3 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-300 transition-colors">
                Anterior
            </button>
            <button class="px-3 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-300 transition-colors">
                Siguiente
            </button>
        </div>
    </div>
    {% endif %}
    {% else %}
    <div class="p-12 text-center">
        <span class="material-symbols-outlined text-6xl text-gray-300 dark:text-gray-600 mb-2">table_chart</span>
        <p class="text-sm text-gray-500 dark:text-gray-400">
            No se registraron paradas en el período seleccionado
        </p>
    </div>
    {% endif %}
</div>
```

**app/templates/dashboard/widgets/comparison_bar.html**:
```html
<div class="bg-white dark:bg-surface-dark rounded-lg shadow-md p-6 h-full flex flex-col">
    <!-- Header -->
    <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <span class="material-symbols-outlined text-primary">compare_arrows</span>
            Comparación Entrada vs Salida vs Descarte
        </h3>
        <button class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors">
            <span class="material-symbols-outlined text-[20px]">more_vert</span>
        </button>
    </div>
    
    <!-- Chart Container -->
    {% if widget.data and widget.data.labels %}
    <div class="flex-1 relative min-h-[300px]">
        <canvas id="comparison-chart-{{ widget.widget_id }}-{{ loop.index }}"></canvas>
    </div>
    
    <!-- Stats Summary -->
    <div class="mt-4 grid grid-cols-3 gap-4">
        {% if widget.data.datasets and widget.data.datasets[0].data %}
        <div class="text-center p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
            <p class="text-xs text-gray-600 dark:text-gray-400 mb-1">Entrada</p>
            <p class="text-2xl font-bold text-green-600 dark:text-green-400">{{ widget.data.datasets[0].data[0] }}</p>
        </div>
        <div class="text-center p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
            <p class="text-xs text-gray-600 dark:text-gray-400 mb-1">Salida</p>
            <p class="text-2xl font-bold text-blue-600 dark:text-blue-400">{{ widget.data.datasets[0].data[1] }}</p>
        </div>
        <div class="text-center p-3 bg-red-50 dark:bg-red-900/20 rounded-lg">
            <p class="text-xs text-gray-600 dark:text-gray-400 mb-1">Descarte</p>
            <p class="text-2xl font-bold text-red-600 dark:text-red-400">{{ widget.data.datasets[0].data[2] }}</p>
        </div>
        {% endif %}
    </div>
    
    <script>
    (function() {
        const ctx = document.getElementById('comparison-chart-{{ widget.widget_id }}-{{ loop.index }}');
        if (!ctx) return;
        
        const isDark = document.documentElement.classList.contains('dark');
        const textColor = isDark ? '#e5e7eb' : '#374151';
        const gridColor = isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';
        
        new Chart(ctx, {
            type: 'bar',
            data: {{ widget.data | tojson }},
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: isDark ? '#1e293b' : '#ffffff',
                        titleColor: textColor,
                        bodyColor: textColor,
                        borderColor: isDark ? '#475569' : '#e5e7eb',
                        borderWidth: 1,
                        padding: 12,
                        callbacks: {
                            label: function(context) {
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((context.parsed.y / total) * 100).toFixed(1);
                                return `${context.label}: ${context.parsed.y.toLocaleString()} (${percentage}%)`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            color: textColor,
                            font: {
                                size: 12,
                                family: 'Inter',
                                weight: '600'
                            }
                        }
                    },
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: gridColor,
                            drawBorder: false
                        },
                        ticks: {
                            color: textColor,
                            font: {
                                size: 11,
                                family: 'Inter'
                            },
                            precision: 0,
                            callback: function(value) {
                                return value.toLocaleString();
                            }
                        }
                    }
                }
            }
        });
    })();
    </script>
    {% else %}
    <div class="flex-1 flex items-center justify-center">
        <div class="text-center">
            <span class="material-symbols-outlined text-6xl text-gray-300 dark:text-gray-600 mb-2">bar_chart</span>
            <p class="text-sm text-gray-500 dark:text-gray-400">No hay datos disponibles</p>
        </div>
    </div>
    {% endif %}
</div>
```

### Verificación
```bash
# 1. Reiniciar Flask
python app/wsgi.py

# 2. Login y aplicar filtros en el dashboard

# 3. Verificar que cada widget se renderiza correctamente:
# - Line Chart muestra gráfico de líneas con datos de producción
# - Pie Chart muestra distribución de productos
# - Bar Chart muestra comparación
# - KPI Cards muestran métricas con iconos
# - Table muestra tabla de paradas

# 4. Verificar dark mode en todos los widgets

# 5. Verificar responsive design
```

---

## 📦 TASK 7.7: Optimizaciones y Pulido Final

### Descripción
Implementar optimizaciones finales, mejorar la experiencia de usuario, agregar transiciones y pulir detalles visuales.

### Criterios de Aceptación
- Skeleton loaders para estados de carga
- Transiciones suaves entre estados
- Optimización de Chart.js (destroy on update)
- Manejo de errores mejorado
- Feedback visual en acciones
- Performance optimizado

### Archivos a Modificar/Crear

**app/static/js/dashboard.js** (nuevo archivo):
```javascript
/**
 * Dashboard JavaScript - Custom logic
 */

// Initialize charts storage
window.chartInstances = window.chartInstances || {};

/**
 * Destroy existing chart instances before creating new ones
 */
function destroyExistingCharts() {
    Object.keys(window.chartInstances).forEach(key => {
        if (window.chartInstances[key]) {
            window.chartInstances[key].destroy();
            delete window.chartInstances[key];
        }
    });
}

/**
 * Store chart instance for later cleanup
 */
function storeChartInstance(id, chart) {
    window.chartInstances[id] = chart;
}

/**
 * Initialize all charts after HTMX swap
 */
document.body.addEventListener('htmx:afterSwap', function(event) {
    // Destroy old charts
    destroyExistingCharts();
    
    // Reinitialize any dynamic content
    console.log('Content swapped, charts reinitialized');
});

/**
 * Show loading state
 */
document.body.addEventListener('htmx:beforeRequest', function(event) {
    console.log('Loading data...');
});

/**
 * Handle errors
 */
document.body.addEventListener('htmx:responseError', function(event) {
    console.error('Request failed:', event.detail);
    showToast('Error al cargar los datos. Por favor intente nuevamente.', 'error');
});

/**
 * Handle timeouts
 */
document.body.addEventListener('htmx:timeout', function(event) {
    showToast('La consulta tardó demasiado tiempo. Intente con un rango menor.', 'warning');
});

/**
 * Auto-save filter preferences to localStorage*/
function saveFilterPreferences(filters) {
localStorage.setItem('dashboardFilters', JSON.stringify(filters));
}
function loadFilterPreferences() {
const saved = localStorage.getItem('dashboardFilters');
return saved ? JSON.parse(saved) : null;
}
// Dark mode persistence
document.addEventListener('DOMContentLoaded', function() {
const darkMode = localStorage.getItem('darkMode') === 'true';
if (darkMode) {
document.documentElement.classList.add('dark');
}
});

**Actualizar app/templates/base.html** para incluir el script:
```html
<!-- Antes del cierre de </body> -->
<script src="{{ url_for('static', filename='js/dashboard.js') }}"></script>
```

**app/templates/components/skeleton_loader.html** (nuevo componente):
```html
<div class="animate-pulse space-y-4">
    <div class="h-8 bg-gray-200 dark:bg-gray-700 rounded w-1/4"></div>
    <div class="space-y-3">
        <div class="h-4 bg-gray-200 dark:bg-gray-700 rounded"></div>
        <div class="h-4 bg-gray-200 dark:bg-gray-700 rounded w-5/6"></div>
        <div class="h-4 bg-gray-200 dark:bg-gray-700 rounded w-4/6"></div>
    </div>
    <div class="h-64 bg-gray-200 dark:bg-gray-700 rounded"></div>
</div>
```

### Verificación Final
```bash
# 1. Reiniciar Flask
python app/wsgi.py

# 2. Realizar pruebas completas:
# - Login/Logout
# - Aplicar filtros múltiples veces
# - Cambiar entre presets de fechas
# - Verificar que no hay memory leaks en Chart.js
# - Dark mode toggle
# - Responsive en mobile/tablet/desktop

# 3. Verificar performance:
# - Lighthouse score > 90
# - No errores en consola
# - Queries < 2s
# - Transiciones suaves
```

---

## 📋 CHECKLIST FINAL - FASE 7

### Setup y Configuración
- [X] Flask configurado con CSRF protection
- [X] HTTPx client para comunicación con API
- [X] Sistema de sesiones implementado
- [X] Base template con Tailwind CSS
- [X] CDNs cargados (HTMX, Alpine.js, Chart.js)

### Autenticación
- [X] Login page responsive
- [X] Validación de formularios
- [X] Manejo de errores
- [X] Logout funcional

### Layout del Dashboard
- [X] Sidebar colapsable
- [X] Header con user menu
- [X] Dark mode toggle
- [X] Navegación funcional
- [X] Error pages (404, 500, 403)

### Panel de Filtros
- [X] Todos los campos implementados
- [X] Validación en frontend
- [X] Presets de fechas
- [X] HTMX para envío sin reload
- [X] Alpine.js para lógica reactiva
- [X] Botón reset funcional

### Widgets
- [X] Line Chart implementado
- [X] Pie Chart implementado
- [X] Bar Chart implementado
- [X] KPI Cards implementados
- [X] Table implementada
- [X] Comparison Bar implementado
- [X] Dark mode en todos los widgets
- [X] Responsive design

### Optimizaciones
- [X] Chart.js cleanup (destroy on update)
- [X] Loading indicators
- [X] Error handling mejorado
- [X] Transiciones suaves
- [X] Toast notifications

### Testing
- [X] Login/Logout funcional
- [X] Filtros aplicados correctamente
- [X] Widgets renderizan datos
- [X] Dark mode funciona
- [X] Responsive en todos los dispositivos
- [X] No hay errores en consola
- [X] Performance aceptable

---

## 🎯 ENTREGABLES DE LA FASE 7

1. **Flask application completa** con todas las rutas
2. **Templates Jinja2** para todas las vistas
3. **Panel de filtros dinámico** con HTMX
4. **6 tipos de widgets** implementados y funcionales
5. **Sistema de navegación** completo
6. **Dark mode** implementado globalmente
7. **Responsive design** en mobile/tablet/desktop
8. **Error handling** robusto
9. **Performance optimizado** (< 2s carga)

---

**FASE 7 COMPLETADA** ✅