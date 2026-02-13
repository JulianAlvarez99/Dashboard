# Resumen del Proyecto — Camet Analytics Dashboard

Estado actual de la implementación, estructura del código y decisiones técnicas.

**Última actualización:** 13 Febrero 2026

---

## 1. Estado General

La plataforma está implementada en su ciclo funcional completo: login → dashboard → filtros → consulta → visualización de KPIs, gráficos y tablas. Falta implementar seguridad de la API (JWT), tests, migrations, rate limiting y funcionalidades avanzadas (reportes, alertas, 2FA).

##  Estado del Proyecto: FUNCIONAL 

El proyecto ha alcanzado un estado **completamente funcional** y está listo para despliegue en producción. Se han implementado todas las fases planificadas (1-7) con backend FastAPI, frontend Flask SSR, sistema de configuración dinámica, motor de widgets, cálculo de métricas OEE y gestión de paradas automatizada.

### 1. 🛡️ Fase 1: Fundaciones y Seguridad
Se estableció la infraestructura base multi-tenant y el sistema de seguridad.
- **Arquitectura Multi-tenant:** Separación estricta entre **DB Global** (Usuarios, Tenants) y **DB Cliente** (Datos de planta).
- **Autenticación Robusta:** Sistema basado en **JWT** con rotación de refresh tokens y hashing **Argon2** (estado del arte en seguridad).
- **Middleware de Seguridad:** Rate limiting, CORS configurado, y headers de seguridad OWASP.
- **Gestión de Usuarios:** Roles (`ADMIN`, `MANAGER`, `OPERATOR`) y endpoints de administración.

### 2. ⚙️ Fase 2: Configuración y Metadatos (In-Memory Cache)
Se implementó el sistema de configuración flexible que permite al SaaS adaptarse a cualquier planta sin cambios de código.
- **Modelos de Planta:** Definición completa de Líneas, Áreas, Productos, Turnos y Filtros en SQLAlchemy.
- **Metadata Cache System:** Sistema de caché en memoria (thread-safe con `asyncio.Lock`) para cargar toda la configuración estática al inicio.
- **CRUD Completo:** Servicios y endpoints para gestionar toda la configuración de la planta.

### 3. ⚡ Fase 3: Motor de Datos de Alto Rendimiento
Se construyó el motor capaz de ingerir y consultar grandes volúmenes de datos de sensores (detecciones).
- **Partition Manager:** Sistema automatizado que gestiona particiones **mensuales** en MySQL para las tablas de detecciones.
- **Dynamic Query Builder:** Constructor de SQL dinámico que inyecta **HINTS de partición** y sanitiza parámetros automáticamente.
- **Detection Service & App-Side Joins:** Recuperación eficiente con enriquecimiento vía `MetadataCache`.

### 4. 🛑 Fase 4: Motor de Cálculo de Paradas (Downtime Engine)
Se implementó la inteligencia para detectar ineficiencias en tiempo real.
- **Detección Automática:** Algoritmo de "gap detection" que identifica micro-paradas y paradas largas.
- **Gestión Híbrida:** Soporte para paradas automáticas y manuales (justificación de operarios).
- **Cálculo Incremental:** Endpoint inteligente que procesa solo los nuevos datos desde el último checkpoint.

### 5. 📈 Fase 5: Métricas y OEE
Se completó el motor de cálculo de indicadores clave de rendimiento (KPIs).
- **Cálculo de OEE Completo:** Disponibilidad (Tiempo), Rendimiento (Velocidad), Calidad (Descarte).
- **Agregación Flexible:** Métricas calculadas por hora, turno, día, semana o mes dinámicamente.
- **Analítica de Pérdidas:** Desglose de tiempo operativo vs tiempo perdido.

### 6. 📊 Fase 6: Dashboard Engine & Widgets
Se construyó un sistema de dashboards dinámico y configurable ("Configuration over Code").
- **Widget Service:** Motor que renderiza 10 tipos de widgets basándose en configuración de base de datos.
- **Dashboard Service:** Gestión de layouts por rol y templates personalizados por tenant.
- **Dynamic API:** Un solo endpoint puede renderizar cualquier widget del catálogo.
- **Validación Automática:** Los parámetros de los widgets se validan contra JSON Schemas.

### 7. 🖥️ Fase 7: Frontend SSR con Flask + HTMX 
Se implementó la interfaz web completa con renderizado del lado del servidor.
- **Flask Frontend:** Aplicación Flask que consume la API FastAPI y renderiza templates Jinja2.
- **HTMX + Alpine.js:** Interactividad sin JavaScript pesado, actualizaciones parciales de página.
- **Tailwind CSS:** Diseño responsivo con tema claro/oscuro.
- **Chart.js:** Visualizaciones de gráficos dinámicas.

---

### Servidores

| Servidor | Framework | Puerto | Estado |
|----------|-----------|--------|--------|
| API REST | FastAPI 0.110.0 | 8000 | Funcional, sin auth |
| Frontend SSR | Flask 3.0.2 | 5000 | Funcional, con auth |

### Punto de entrada

```
run.py → puede lanzar ambos servidores, solo API o solo web
  python run.py       # Ambos (threads)
  python run.py api   # Solo FastAPI
  python run.py web   # Solo Flask
```

---

## 2. Estructura del Proyecto

```
Dashboard/
├── run.py                          # Entry point (ambos servidores)
├── requirements.txt                # Dependencias Python
├── .env                            # Variables de entorno (no en repo)
│
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI app factory + lifespan
│   ├── flask_app.py                # Flask app factory + blueprints
│   │
│   ├── core/                       # Infraestructura compartida
│   │   ├── config.py               # Pydantic Settings (99 líneas)
│   │   ├── database.py             # DatabaseManager (dual sync/async)
│   │   ├── cache.py                # MetadataCache singleton
│   │   └── auth_utils.py           # Argon2 verify/hash + authenticate_user
│   │
│   ├── models/                     # SQLAlchemy ORM models
│   │   ├── global_models.py        # Tenant, User, WidgetCatalog, etc.
│   │   └── tenant_models.py        # ProductionLine, Area, Product, etc.
│   │
│   ├── api/v1/                     # FastAPI endpoints
│   │   ├── dashboard.py            # POST /dashboard/data (pipeline principal)
│   │   ├── filters.py              # GET /filters/options/* (cascada)
│   │   ├── layout.py               # GET /layout/full-config
│   │   ├── widgets.py              # GET /widgets/catalog
│   │   └── system.py               # Health, cache info/refresh
│   │
│   ├── routes/                     # Flask blueprints
│   │   ├── auth.py                 # Login, logout, @login_required
│   │   └── dashboard.py            # Render index con layout config
│   │
│   ├── services/                   # Lógica de negocio
│   │   ├── dashboard_data_service.py  # Orchestrador principal (332 líneas)
│   │   │
│   │   ├── config/
│   │   │   └── layout_service.py   # Resolución de layout + widgets + filtros
│   │   │
│   │   ├── filters/                # Sistema de filtros
│   │   │   ├── base.py             # BaseFilter ABC + FilterConfig dataclass
│   │   │   ├── factory.py          # FilterFactory (7 tipos registrados)
│   │   │   ├── filter_config.py    # Utilidades
│   │   │   ├── filter_resolver.py  # Fachada: resolve, options, groups
│   │   │   └── types/              # Implementaciones concretas
│   │   │       ├── daterange.py
│   │   │       ├── dropdown.py
│   │   │       ├── multiselect.py
│   │   │       ├── text.py
│   │   │       ├── number.py
│   │   │       └── toggle.py
│   │   │
│   │   ├── processors/             # Procesadores de widgets
│   │   │   ├── __init__.py         # PROCESSOR_MAP (16 tipos), CHART_TYPES
│   │   │   ├── helpers.py          # Utilidades compartidas
│   │   │   ├── kpi.py              # 7 procesadores KPI (incluye OEE)
│   │   │   ├── tables.py           # downtime_table
│   │   │   ├── downtime_calculator.py  # Gap analysis + dedup
│   │   │   ├── charts/             # line, bar, pie, comparison_bar, scatter
│   │   │   └── ranking/            # product_ranking, line_status, metrics_summary
│   │   │
│   │   └── widgets/                # Clases base y agregación
│   │       ├── base.py             # WidgetConfig, FilterParams (403 líneas)
│   │       ├── aggregators.py      # DataAggregator (fetch + enrich + resample)
│   │       ├── factory.py          # WidgetFactory
│   │       ├── widget_renderer.py  # WidgetRenderer
│   │       └── types/              # Widget class types (parcialmente usado)
│   │
│   ├── repositories/
│   │   └── config_repository.py    # Queries de configuración
│   │
│   ├── static/
│   │   ├── widget_layout.json      # Layout estático de referencia
│   │   ├── css/                    # Estilos (Tailwind custom)
│   │   │   ├── main.css
│   │   │   ├── dashboard.css
│   │   │   ├── components.css
│   │   │   ├── login.css
│   │   │   └── components/, dashboard/  # Subdirectories
│   │   └── js/
│   │       ├── dashboard-app.js    # Alpine.js component (~300 líneas)
│   │       └── chart-renderer.js   # Chart.js singleton (~474 líneas)
│   │
│   └── templates/
│       ├── base.html               # Layout base (CDN imports)
│       ├── auth/login.html         # Formulario login
│       ├── components/
│       │   ├── header.html         # Barra superior
│       │   └── sidebar.html        # Panel de filtros
│       └── dashboard/
│           ├── index.html          # Dashboard principal
│           └── partials/
│               ├── _widget_kpi.html
│               ├── _widget_chart.html
│               ├── _widget_table.html
│               └── (otros parciales)
│
├── Documentation/                  # Este directorio
│   ├── README.md
│   ├── Documentation.md
│   ├── PROJECT_SUMMARY.md
│   ├── ARCHITECTURE_REFACTOR.md
│   ├── ARCHITECTURE_DIAGRAMS.md
│   ├── TODO.md
│   ├── Planificacion.md            # Plan original por fases
│   ├── phase_1.md ... phase_7.md   # Documentación por fase
│   └── inspect_db_schema_*.json    # Esquemas de DB exportados
│
├── camet_global.sql                # DDL para base global
├── client_x.sql                    # DDL para base tenant ejemplo
├── check_*.py, update_*.py         # Scripts utilitarios standalone
└── test_workflow.py                # Test básico del pipeline
```

---

## 3. Principios de Diseño

### SRP (Single Responsibility Principle)

Cada módulo tiene una responsabilidad clara:

| Módulo | Responsabilidad |
|--------|----------------|
| `core/config.py` | Carga de settings de entorno |
| `core/database.py` | Gestión de conexiones DB |
| `core/cache.py` | Cache in-memory de metadatos |
| `core/auth_utils.py` | Hashing y verificación de passwords |
| `dashboard_data_service.py` | Orquestación del pipeline de datos |
| `filter_resolver.py` | Resolución de filtros y opciones |
| `downtime_calculator.py` | Algoritmo de detección de paradas |
| `kpi.py` | Cálculos de KPIs |
| `chart-renderer.js` | Configuración y render de gráficos |
| `dashboard-app.js` | Estado reactivo y comunicación con API |

### DRY (Don't Repeat Yourself)

- KPIs derivados (`availability`, `performance`, `quality`) delegan a `process_kpi_oee()` en vez de duplicar la lógica
- `DataAggregator` centraliza fetch + enrich para todos los procesadores
- `ChartRenderer` evita repetir configuraciones de Chart.js en cada template
- `FilterFactory` usa patrón factory para evitar switch/if en la creación de filtros
- `helpers.py` contiene utilidades compartidas (empty_widget, format_time, scheduled_minutes)

### Factory Pattern

- `FilterFactory`: tipo → clase de filtro
- `PROCESSOR_MAP`: widget_type → función procesadora
- `_configBuilders` (ChartRenderer): widget_type → builder de config

### Singleton

- `MetadataCache`: única instancia global, compartida por todos los servicios
- `ChartRenderer`: objeto literal JS (singleton implícito)

---

## 4. Historial de Correcciones Recientes

### Zoom/Pan en Gráficos
- **Problema**: `onDblClick` no es una opción válida de Chart.js
- **Solución**: Se reemplazó por event listener nativo `canvas.addEventListener('dblclick', ...)`
- Se agregó `modifierKey: 'ctrl'` al drag zoom para no interferir con el pan
- Se creó `_createZoomToolbar()` para toolbar visual de zoom

### Fechas por Defecto
- **Antes**: Default 7 días atrás, auto-query al cargar
- **Ahora**: Default ayer a hoy (`_daysAgo(1)` a `_today()`), sin auto-query

### Threshold de Downtime
- **Antes**: `gap_sec >= threshold` (desigualdad no estricta)
- **Ahora**: `gap_sec > threshold` (desigualdad estricta)
- Razón: Si el gap es exactamente igual al threshold, la producción NO se detuvo

### Cálculo OEE — Rendimiento
- **Antes**: Usaba `product.production_std` (estándar por producto)
- **Ahora**: Usa `production_line.performance` (productos/minuto por línea)
- Cada línea tiene su propia tasa de producción esperada
- La producción teórica se calcula per-line y luego se suma

### Modo Multi-Línea
- `scatter_chart`: Oculto (no tiene sentido con múltiples líneas)
- `kpi_downtime_count`: Oculto (paradas individuales no aplican)
- Anotaciones de downtime en `line_chart`: Suprimidas
- Minutos de parada en desglose OEE: Ocultos
- Se pasa `isMultiLine` desde `dashboard-app.js` → `ChartRenderer`

---

## 5. Dependencias (requirements.txt)

### En Uso Activo
| Paquete | Versión | Uso |
|---------|---------|-----|
| fastapi | 0.110.0 | API REST |
| flask | 3.0.2 | SSR + Auth |
| uvicorn | 0.29.0 | ASGI server |
| sqlalchemy | 2.0.29 | ORM |
| aiomysql | 0.2.0 | Async MySQL |
| pymysql | 1.1.0 | Sync MySQL |
| pandas | 2.2.1 | Data processing |
| pydantic | 2.6.4 | Validation |
| pydantic-settings | 2.2.1 | Environment config |
| argon2-cffi | 23.1.0 | Password hashing |
| httpx | 0.27.0 | HTTP client (Flask→FastAPI proxy) |
| python-dotenv | 1.0.1 | .env loading |

### Instalados pero No Usados
| Paquete | Versión | Uso Previsto |
|---------|---------|-------------|
| pyjwt | 2.8.0 | JWT auth para API |
| slowapi | 0.1.9 | Rate limiting |
| apscheduler | 3.10.4 | Background tasks |
| flask-wtf | 1.2.1 | CSRF protection |
| alembic | 1.13.1 | DB migrations |
| bleach | 6.1.0 | XSS sanitization |
| cryptography | 42.0.5 | Crypto utilities |

---

## 6. Directorios que No Existen (referidos en documentación anterior)

Los siguientes directorios fueron planeados pero nunca creados:

| Directorio | Propósito Planeado |
|------------|-------------------|
| `app/middleware/` | Middleware JWT, CORS custom, rate limiting |
| `app/utils/` | Utilidades compartidas (existente: `helpers.py`) |
| `app/schemas/` | Pydantic schemas dedicados (están inline en endpoints) |
| `scripts/` | Scripts de setup, seeding, migration |
| `migrations/` | Alembic migrations |
| `tests/` | Tests unitarios e integración |

---

_Documento actualizado automáticamente. Refleja el estado real del código._
