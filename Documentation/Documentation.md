Documentación Técnica: Dashboard SaaS Industrial 
1. Arquitectura del Sistema
1.1. Filosofía de Diseño: "Motor de Reglas"
El sistema sigue el principio de Configuration over Code. La aplicación Python actúa como un motor genérico que interpreta la configuración almacenada en la base de datos (tablas DASHBOARD_TEMPLATE, WIDGET_CATALOG, TENANT) para renderizar la interfaz y procesar datos sin lógica hardcoded específica por cliente.
1.2. Estrategia de Datos: "Application-Side Joins"
Para optimizar el rendimiento en entornos MySQL estándar (cPanel):
No se realizan JOINs masivos en Base de Datos para la tabla de detecciones.
Carga de Metadatos: Tablas como PRODUCT, AREA y PRODUCTION_LINE se cargan en memoria/caché al iniciar la API.
Enriquecimiento en Aplicación: Los IDs numéricos de la tabla de hechos se resuelven contra los metadatos en memoria usando Pandas/FastAPI.

2. Esquema de Base de Datos
El esquema está organizado en 4 Áreas Temáticas (Subject Areas) según el modelo.

Módulo 1: Identidad y Enrutamiento (Auth)
Responsabilidad: Gestión de acceso, auditoría y configuración base del inquilino (Tenant).
Tabla
Descripción
Campos Clave y Cambios
TENANT 
Representa al Cliente/Empresa.
config_tenant (JSON) para personalización global visual o de comportamiento.
USER 
Usuarios del sistema.
permissions (JSON) para RBAC granular. Vinculado a tenant_id.


AUDIT_LOG 
Log de seguridad inmutable.
Registra action, ip_address y details (JSON) de eventos críticos.
USER_LOGIN 
Historial de sesiones.
Separa el acceso (login_at, logout_at) de la auditoría operativa.
USER_QUERY 
Auditoría de consultas de datos.
Registra filtros exactos usados: sql_query, start_date, line, interval_type para trazabilidad de uso de datos.

Módulo 2: Definición de Planta (Production)
Responsabilidad: Modelado lógico de la planta física y reglas de negocio.
Tabla
Descripción
Campos Clave y Cambios
PRODUCTION_LINE 
Líneas de producción.
Incluye métricas base OEE: availability, performance y el downtime_threshold específico.
AREA 
Estaciones lógicas de detección.
Incluye coord_x1, coord_y1, etc., para mapeo visual en el dashboard. Relación con PRODUCTION_LINE.


PRODUCT 
Catálogo de productos.
Datos físicos como product_weight y product_color para gráficos.
SHIFT 
Configuración de Turnos.
days_implemented (JSON) para rotaciones complejas y flags de is_overnight.
FILTER 
Filtros disponibles para el cliente.
default_value (JSON) y additional_filter (JSON) para lógica de UI flexible.
FAILURE / INCIDENT 


Gestión de Mantenimiento.
Catálogo de tipos de fallas (type_failure JSON) y registro de incidentes con campo solution y has_solution.



Módulo 3: Big Data (Detecciones Dinámicas)
Responsabilidad: Almacenamiento masivo optimizado.
Tabla
Descripción
Estrategia
DETECTION_LINE_X 
Tabla Dinámica. No existe una única tabla. Se crea una por línea (CREATE TABLE detections_line_X).
PK: detection_id, detected_at (Timestamp).

Columnas ligeras: area_id, product_id. Sin FKs estrictas a nivel de motor para velocidad.
DOWNTIME_EVENTS_ 
Eventos de parada procesados.
Persiste duration, start_time, end_time y reason_code para evitar cálculos en tiempo real sobre la tabla de detecciones.

Módulo 4: Configuración de UI (Dashboarding)
Responsabilidad: Definición de la interfaz visual dirigida por datos.
Tabla
Descripción
Detalles
WIDGET_CATALOG 
Metadatos del sistema (Solo lectura).
Define widget_type y required_params (JSON Schema) para que el frontend sepa qué renderizar.
DASHBOARD_TEMPLATE 
Configuración por Rol/Cliente.
layout_config (JSON) define el mapa de la pantalla (posiciones X, Y, tamaños) asignado a un role_access específico.

Módulo 5: Configuración y Monitoreo del Sistema (System)
Responsabilidad: Salud del hardware y configuración técnica.
Tabla
Descripción
Campos Clave
SYSTEM_CONFIG 
Key-Value store del sistema.
key y value (JSON) para configuraciones de backend.
SYSTEM_MONITOR 
Telemetría del servidor.
cpu_usage, ram_usage, gpu_temp, gpu_mem_used_bytes. Vital para monitoreo de recursos en procesamiento IA/Visión.
CAMERA_CONTROL_EVENT 
Auditoría de Hardware.
Registra acciones sobre cámaras (action, reason) y uso de GPU asociado.
CAMERA_AREA 
Mapeo Físico-Lógico.
Vincula camara_id (Hardware) con area_id (Lógica) y su estado.


3. Restricciones y Reglas
Tablas Dinámicas: La aplicación Python gestiona el ciclo de vida (DDL) de las tablas DETECTION_LINE_X.
Integridad Relajada: Las tablas de alto volumen (DETECTION, SYSTEM_MONITOR) priorizan la velocidad de inserción sobre las restricciones de clave foránea (FOREIGN KEY) estrictas en la base de datos.
JSON fields: Se hace uso extensivo de campos JSON (config_tenant, permissions, layout_config) para permitir flexibilidad futura sin migraciones de esquema complejas (Schema Evolution).
Particionamiento: Las tablas DETECTION_LINE_X deben implementar particionamiento por rango de fechas (Range Partitioning) para gestión de histórico.
📊 Arquitectura Final del Sistema
Stack Tecnológico Confirmado
Backend:
├── FastAPI (API REST + WebSockets para real-time)
├── Flask (Server-Side Rendering con Jinja2)
├── SQLAlchemy 2.0+ (ORM con async support)
├── Pydantic v2 (Validación de datos)
├── Python 3.12+
Frontend:
├── Jinja2 Templates
├── HTMX (interactividad sin JS pesado)
├── Alpine.js (lógica mínima client-side)
├── Chart.js (gráficos ligeros)
├── Tailwind CSS (styling optimizado)

Seguridad:
├── Passlib + Argon2 (hashing)
├── PyJWT (tokens)
├── python-multipart (CSRF)
├── slowapi (rate limiting)
Base de Datos:
├── MySQL 8.0+
├── Particionamiento por RANGE (mensual)
├── In-memory cache (functools + dict)


Estructura de Proyecto

dashboard-saas/
│
├── .env.example                    # Template de variables de entorno
├── .env.development               # Configuración local
├── .env.production                # Configuración cPanel
├── requirements.txt               # Dependencias Python
├── Dockerfile                     # Opcional para desarrollo
├── docker-compose.yml             # Opcional para desarrollo
├── README.md
├── TODO.md                        # Lista de tareas futuras
│
├── app/
│   ├── __init__.py
│   ├── main.py                    # Entry point FastAPI
│   ├── wsgi.py                    # Entry point Flask (producción)
│   │
│   ├── core/                      # Configuración central
│   │   ├── __init__.py
│   │   ├── config.py              # Settings (BaseSettings de Pydantic)
│   │   ├── security.py            # JWT, hashing, CSRF
│   │   ├── database.py            # Conexiones DB (global + clients)
│   │   ├── cache.py               # Sistema de caché in-memory
│   │   ├── logging.py             # Configuración de logs
│   │   └── dependencies.py        # Dependency injection (get_db, get_current_user)
│   │
│   ├── models/                    # SQLAlchemy Models
│   │   ├── __init__.py
│   │   ├── base.py                # Base declarativa
│   │   ├── global_db/             # Modelos DB_GLOBAL
│   │   │   ├── __init__.py
│   │   │   ├── tenant.py
│   │   │   ├── user.py
│   │   │   ├── audit.py
│   │   │   └── template.py        # WIDGET_CATALOG, DASHBOARD_TEMPLATE
│   │   └── client_db/             # Modelos DB_CLIENT
│   │       ├── __init__.py
│   │       ├── production.py      # PRODUCTION_LINE, AREA
│   │       ├── product.py
│   │       ├── filter.py
│   │       ├── shift.py
│   │       ├── incident.py        # FAILURE, INCIDENT
│   │       ├── detection.py       # Modelo dinámico para DETECTION_LINE_X
│   │       ├── downtime.py        # Modelo dinámico para DOWNTIME_EVENTS_X
│   │       └── system.py          # SYSTEM_CONFIG, SYSTEM_MONITOR
│   │
│   ├── schemas/                   # Pydantic Schemas (request/response)
│   │   ├── __init__.py
│   │   ├── auth.py                # LoginRequest, TokenResponse
│   │   ├── user.py                # UserCreate, UserResponse
│   │   ├── tenant.py
│   │   ├── production.py
│   │   ├── query.py               # QueryFilters, DateRangeRequest
│   │   └── dashboard.py           # WidgetConfig, DashboardLayout
│   │
│   ├── api/                       # Endpoints FastAPI
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py            # /login, /logout, /refresh
│   │   │   ├── users.py           # CRUD usuarios
│   │   │   ├── tenants.py         # CRUD tenants (admin only)
│   │   │   ├── production.py      # CRUD líneas, áreas, productos
│   │   │   ├── data.py            # Consultas de detecciones
│   │   │   ├── dashboard.py       # Endpoints para widgets
│   │   │   └── system.py          # Monitoreo, health checks
│   │
│   ├── services/                  # Lógica de negocio
│   │   ├── __init__.py
│   │   ├── auth_service.py        # Autenticación, generación de tokens
│   │   ├── tenant_service.py      # Gestión de tenants
│   │   ├── cache_service.py       # Precarga de metadatos
│   │   ├── query_builder.py       # Constructor dinámico de queries SQL
│   │   ├── detection_service.py   # Lógica de detecciones + app-side joins
│   │   ├── downtime_service.py    # Cálculo de paradas
│   │   ├── metrics_service.py     # Cálculo de KPIs (OEE, eficiencia)
│   │   ├── widget_service.py      # Interpretación de WIDGET_CATALOG
│   │   └── audit_service.py       # Registro en AUDIT_LOG
│   │
│   ├── repositories/              # Capa de acceso a datos (patrón Repository)
│   │   ├── __init__.py
│   │   ├── base_repository.py     # CRUD genérico
│   │   ├── user_repository.py
│   │   ├── tenant_repository.py
│   │   ├── production_repository.py
│   │   └── detection_repository.py
│   │
│   ├── middleware/                # Middlewares personalizados
│   │   ├── __init__.py
│   │   ├── tenant_context.py      # Inyecta tenant_id en contexto
│   │   ├── audit_middleware.py    # Log automático de requests
│   │   ├── rate_limit.py          # Rate limiting por IP/usuario
│   │   └── security_headers.py    # OWASP headers
│   │
│   ├── utils/                     # Utilidades
│   │   ├── __init__.py
│   │   ├── datetime_helpers.py    # Manejo de turnos, rangos
│   │   ├── validators.py          # Validaciones custom
│   │   ├── partition_manager.py   # Gestión de particiones MySQL
│   │   └── exceptions.py          # Excepciones personalizadas
│   │
│   ├── templates/                 # Jinja2 Templates (Flask)
│   │   ├── base.html              # Layout principal
│   │   ├── auth/
│   │   │   ├── login.html
│   │   │   └── logout.html
│   │   ├── dashboard/
│   │   │   ├── index.html         # Dashboard principal
│   │   │   ├── filters.html       # Panel de filtros
│   │   │   └── widgets/           # Widgets individuales
│   │   │       ├── production_chart.html
│   │   │       ├── kpi_cards.html
│   │   │       ├── comparison_bar.html
│   │   │       ├── product_pie.html
│   │   │       └── downtime_table.html
│   │   ├── admin/
│   │   │   ├── tenants.html
│   │   │   ├── users.html
│   │   │   └── config.html
│   │   └── errors/
│   │       ├── 404.html
│   │       ├── 500.html
│   │       └── 403.html
│   │
│   ├── static/                    # Archivos estáticos
│   │   ├── css/
│   │   │   ├── tailwind.min.css   # Build de Tailwind
│   │   │   └── custom.css
│   │   ├── js/
│   │   │   ├── htmx.min.js
│   │   │   ├── alpine.min.js
│   │   │   ├── chart.min.js
│   │   │   └── dashboard.js       # Lógica custom
│   │   └── img/
│   │       └── logo.svg
│   │
│   └── tasks/                     # Background tasks (Celery/APScheduler)
│       ├── __init__.py
│       ├── downtime_calculator.py # Calcula paradas periódicamente
│       ├── partition_maintenance.py # Crea/elimina particiones
│       └── cache_refresh.py       # Actualiza caché de metadatos
│
├── migrations/                    # Alembic migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── 001_initial_global_db.py
│       └── 002_initial_client_db_template.py
│
├── scripts/                       # Scripts de utilidad
│   ├── init_db.py                 # Inicializa DBs y particiones
│   ├── create_tenant.py           # Script para crear nuevo tenant
│   ├── seed_data.py               # Datos de prueba
│   └── backup_db.sh               # Backup automático
│
└── tests/                         # Tests
    ├── __init__.py
    ├── conftest.py                # Fixtures pytest
    ├── test_auth.py
    ├── test_queries.py
    ├── test_downtime.py
    └── test_widgets.py
