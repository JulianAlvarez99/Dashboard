# 📊 Dashboard SaaS Industrial — Camet Analytics

Plataforma multi-tenant de monitoreo industrial en tiempo real para líneas de producción con visión artificial. Visualiza métricas de producción, calcula KPIs (OEE: Disponibilidad, Rendimiento, Calidad) y gestiona paradas de línea de forma automatizada y escalable.

**Versión:** 2.0.0  
**Última actualización:** 25 Febrero 2026  
**Python:** 3.12+  
**Módulo principal:** `new_app/`  
**Entry point:** `run_new.py`

---

## 🏗️ Arquitectura del Sistema

Arquitectura **dual-server** con separación clara de responsabilidades:

| Componente | Framework | Puerto | Rol |
|------------|-----------|--------|-----|
| **API de Datos** | FastAPI | 8000 | REST API async, pipeline de datos, cálculo de métricas |
| **Frontend SSR** | Flask | 5000 | Renderizado de templates, autenticación, sesiones |

### Multi-Tenancy con Bases de Datos Aisladas

```
┌──────────────────────────────────────────────────────────────────┐
│                        CLIENTE (Browser)                          │
│         Alpine.js 3.x · Chart.js 4.4 · Tailwind CSS              │
│   dashboard-app.js · chart-renderer.js · dashboard-orchestrator  │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                     FLASK (Puerto 5000)                           │
│      Session-based Auth · Jinja2 SSR · @login_required           │
└──────────────────────────┬───────────────────────────────────────┘
                           │ API calls directas (Browser → FastAPI)
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                    FASTAPI (Puerto 8000)                          │
│              REST API · CORS · MetadataCache                      │
│  ┌────────────┬────────────┬───────────┬─────────────────────┐  │
│  │ /dashboard │ /filters   │ /layout   │ /system · /broker   │  │
│  └─────┬──────┴─────┬──────┴─────┬─────┴─────────────────────┘  │
│        │             │             │                               │
│  ┌─────▼─────────────▼─────────────▼──────────────────────────┐  │
│  │         DashboardOrchestrator  (Etapa 6 — pipeline.py)      │  │
│  │                                                              │  │
│  │  Phase 6.1  FilterEngine   → validar y normalizar params    │  │
│  │  Phase 6.2  LineResolver   → resolver line_id → [line_ids]  │  │
│  │  Phase 6.3  WidgetResolver → layout → class names           │  │
│  │  Phase 6.4  DetectionSvc   → fetch + enrich detecciones     │  │
│  │  Phase 6.5  DowntimeSvc    → DB downtime + gap analysis     │  │
│  │  Phase 6.6  DataBroker     → rutear datos a cada widget     │  │
│  │  Phase 6.7  WidgetEngine   → auto-discovery + process()     │  │
│  │  Assembly   ResponseAssembler → JSON final                  │  │
│  └──────────────────────────┬─────────────────────────────────┘  │
│                             │                                      │
│  ┌──────────────────────────▼─────────────────────────────────┐  │
│  │           MetadataCache  (In-Memory Singleton)              │  │
│  │  production_lines · areas · products · shifts               │  │
│  │  filters · failures · incidents · widget_catalog            │  │
│  └──────────────────────────┬─────────────────────────────────┘  │
└─────────────────────────────┼──────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────┐
          ▼                                   ▼
┌──────────────────────┐         ┌──────────────────────────────┐
│   camet_global       │         │   db_client_{tenant}         │
│   ───────────        │         │   ──────────────────         │
│   tenant             │         │   production_line            │
│   user               │         │   area / product / shift     │
│   widget_catalog     │         │   filter / failure           │
│   dashboard_template │         │   incident                   │
│   user_login         │         │   detection_line_{name} (N)  │
│   audit_log          │         │   downtime_events_{name} (N) │
└──────────────────────┘         └──────────────────────────────┘
                                 (*) tablas dinámicas por línea
```

---

## 📁 Estructura Real del Proyecto

```
Dashboard/
├── run_new.py                      # Entry point principal
├── requirements.txt
├── .env                            # Variables de entorno (no en repo)
│
├── new_app/                        # Módulo principal
│   ├── main.py                     # FastAPI app factory + lifespan
│   ├── flask_app.py                # Flask app factory + blueprints
│   │
│   ├── core/                       # Infraestructura compartida
│   │   ├── config.py               # Pydantic Settings
│   │   ├── database.py             # DatabaseManager (dual sync/async)
│   │   ├── cache.py                # MetadataCache singleton
│   │   └── auth.py                 # Argon2 hash + authenticate_user
│   │
│   ├── models/                     # SQLAlchemy ORM
│   │   ├── global_models.py        # Tenant, User, WidgetCatalog
│   │   └── tenant_models.py        # ProductionLine, Area, Product, etc.
│   │
│   ├── api/v1/                     # FastAPI endpoints
│   │   ├── __init__.py             # api_router (incluye todos)
│   │   ├── dashboard.py            # POST /dashboard/data (pipeline)
│   │   ├── detections.py           # GET /detections/*
│   │   ├── filters.py              # GET /filters/options/*
│   │   ├── layout.py               # GET /layout/full-config
│   │   ├── broker.py               # POST /broker/data
│   │   ├── system.py               # /system/health, cache/refresh
│   │   └── dependencies.py         # TenantContext, require_tenant
│   │
│   ├── routes/                     # Flask blueprints
│   │   ├── auth.py                 # Login, logout
│   │   └── dashboard.py            # Render index
│   │
│   ├── config/
│   │   ├── widget_layout.py        # GRID_COLUMNS + SHOW_OEE_TAB (solo constantes)
│   │   └── external_apis.yml       # Configuración APIs externas
│   │
│   ├── services/
│   │   ├── orchestrator/           # Coordinador del pipeline
│   │   │   ├── pipeline.py         # DashboardOrchestrator.execute()
│   │   │   ├── resolver.py         # WidgetResolver
│   │   │   ├── context.py          # DashboardContext (inmutable)
│   │   │   └── assembler.py        # ResponseAssembler
│   │   │
│   │   ├── data/                   # Carga y cálculo de datos
│   │   │   ├── detection_service.py
│   │   │   ├── downtime_service.py
│   │   │   ├── downtime_calculator.py   # Gap analysis
│   │   │   ├── enrichment.py            # App-side joins
│   │   │   ├── line_resolver.py
│   │   │   ├── query_builder.py
│   │   │   └── partition_manager.py
│   │   │
│   │   ├── filters/                # Auto-discovery de filtros
│   │   │   ├── base.py             # BaseFilter, FilterConfig
│   │   │   ├── engine.py           # FilterEngine
│   │   │   └── types/              # 16 filtros concretos
│   │   │
│   │   ├── widgets/                # Auto-discovery de widgets
│   │   │   ├── base.py             # BaseWidget, WidgetContext
│   │   │   ├── engine.py           # WidgetEngine
│   │   │   ├── helpers.py          # Utilidades de cálculo
│   │   │   └── types/              # 18 widgets concretos
│   │   │
│   │   ├── broker/                 # DataBroker
│   │   │   ├── data_broker.py
│   │   │   ├── external_api_service.py
│   │   │   └── api_config.py
│   │   │
│   │   └── config/
│   │       └── layout_service.py
│   │
│   ├── static/
│   │   ├── css/dashboard.css
│   │   └── js/
│   │       ├── dashboard-app.js
│   │       ├── chart-renderer.js
│   │       ├── dashboard-orchestrator.js
│   │       ├── dashboard-events.js
│   │       ├── data-engine.js
│   │       └── api-client.js
│   │
│   └── templates/
│       ├── base.html
│       ├── auth/login.html
│       └── dashboard/index.html + partials/
│
├── scripts/
│   ├── check_*.py
│   ├── create_tenant_user.py
│   └── load_detections.py
│
├── Documentation/
├── camet_global.sql
└── client_x.sql
```

---

## 🛠️ Stack Tecnológico

### Backend
| Tecnología | Versión | Uso |
|------------|---------|-----|
| **Python** | 3.12+ | Lenguaje principal |
| **FastAPI** | 0.110.0 | API REST async |
| **Flask** | 3.0.2 | SSR + autenticación |
| **SQLAlchemy** | 2.0+ | ORM async (`aiomysql`) + sync (`pymysql`) |
| **Pydantic** | v2 | Validación de datos, Settings |
| **Pandas** | 2.2+ | Procesamiento de datos, resampling |
| **Uvicorn** | 0.29.0 | ASGI server |

### Frontend (CDN, sin build step)
| Tecnología | Uso |
|------------|-----|
| **Alpine.js 3.x** | Reactividad client-side |
| **Chart.js 4.4** | Gráficos (línea, barra, pie, scatter) |
| **chartjs-plugin-zoom** | Zoom/pan con reset (dblclick nativo) |
| **chartjs-plugin-annotation** | Marcas de paradas |
| **Tailwind CSS** | Estilos utility-first |

### Base de Datos
| Motor | Uso |
|-------|-----|
| **MySQL 8.0+** | Principal |
| **NullPool** | Para cPanel/hosting compartido |
| **Tablas dinámicas** | `detection_line_{name}`, `downtime_events_{name}` por línea |

### Seguridad
| Tecnología | Uso |
|------------|-----|
| **Argon2** | Hashing de contraseñas |
| **Flask Sessions** | Autenticación server-side |
| **CORS** | Restringido a `localhost:5000` |
| **RBAC** | 5 roles: SUPER_ADMIN, ADMIN, MANAGER, OPERATOR, VIEWER |

---

## 🚀 Inicio Rápido

### Requisitos
```bash
pip install -r requirements.txt
```

### Variables de Entorno (.env)
```env
APP_NAME=CametAnalytics
APP_ENV=development
DEBUG=True
SECRET_KEY=your-secret-key
FLASK_SECRET_KEY=your-flask-secret
FLASK_PORT=5000
API_BASE_URL=http://127.0.0.1:8000

GLOBAL_DB_HOST=localhost
GLOBAL_DB_PORT=3306
GLOBAL_DB_NAME=camet_global
GLOBAL_DB_USER=root
GLOBAL_DB_PASSWORD=

TENANT_DB_HOST=localhost
TENANT_DB_PORT=3306
TENANT_DB_NAME=db_client_camet_robotica
TENANT_DB_USER=root
TENANT_DB_PASSWORD=
```

### Ejecutar
```bash
# Ambos servidores simultáneamente
python run_new.py

# Solo API FastAPI (puerto 8000)
python run_new.py api

# Solo Frontend Flask (puerto 5000)
python run_new.py web
```

### Acceso
- **Dashboard:** http://127.0.0.1:5000
- **API Docs:** http://127.0.0.1:8000/api/docs (solo si `DEBUG=True`)
- **Credenciales de prueba:** `admin` / `admin123`

---

## ✅ Estado Actual de Funcionalidades

### Implementado y Funcional
- [x] Arquitectura multi-tenant con aislamiento por DB
- [x] Autenticación session-based con Argon2 + auditoría
- [x] MetadataCache in-memory singleton (carga on-demand post-login)
- [x] DashboardOrchestrator con pipeline de 7 fases
- [x] **Auto-discovery de widgets** via `importlib` (sin registro manual)
- [x] **Auto-discovery de filtros** via `importlib` (sin registro manual)
- [x] DataBroker para rutear datos a fuentes internas o externas
- [x] DashboardContext como contenedor inmutable de datos
- [x] ResponseAssembler que produce el JSON final estándar
- [x] **18 tipos de widgets** (7 KPIs, 5 charts, scatter, table, ranking, indicator, summary, feed)
- [x] **16 tipos de filtros** (daterange, line, product, shift, area, interval, curve, threshold, toggle, etc.)
- [x] Cálculo completo de OEE con lógica DRY (`_compute_oee()`)
- [x] OEE per-line con `production_line.performance`
- [x] Gap analysis para detección automática de paradas
- [x] Modo multi-línea (oculta widgets con `downtime_only: True`)
- [x] Layout por tabs: `produccion` | `oee`
- [x] Grid 4 columnas con `col_span` + `row_span` configurables
- [x] `include_raw=True` para datos crudos en respuesta
- [x] External API support (DataBroker + `external_apis.yml`)
- [x] Zoom/pan interactivo con reset por doble clic
- [x] Overlay de paradas en gráficos de producción
- [x] Scripts utilitarios en `scripts/`

### Pendiente / No Implementado
- [ ] JWT Authentication para FastAPI (API abierta, sin auth)
- [ ] CSRF Protection (`flask-wtf` instalado, no activado)
- [ ] Rate Limiting (`slowapi` instalado, no activado)
- [ ] Suite de tests (`tests/` no existe)
- [ ] Alembic Migrations (`alembic` instalado, no configurado)
- [ ] APScheduler para cálculo automático de downtime
- [ ] Enforcement de roles por endpoint
- [ ] `new_app/utils/` vacío
- [ ] `new_app/static/js/modules/` vacío

---

## 📄 Documentos Relacionados

| Archivo | Descripción |
|---------|-------------|
| [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) | Estado actual de la implementación y decisiones técnicas |
| [ARCHITECTURE_DIAGRAMS.md](ARCHITECTURE_DIAGRAMS.md) | Diagramas técnicos actualizados |
| [WIDGETS_AND_FILTERS.md](WIDGETS_AND_FILTERS.md) | Guía completa: cómo agregar widgets y filtros |
| [TODO.md](TODO.md) | Roadmap y tareas pendientes por prioridad |
| [Documentation.md](Documentation.md) | Documentación técnica extendida |
| [Planificacion_refactor.md](Planificacion_refactor.md) | Plan de refactorización (contexto histórico) |

---

**Proyecto propietario — Camet Robótica. Todos los derechos reservados.**
