# 📊 Dashboard SaaS Industrial — Camet Analytics

Plataforma multi-tenant de monitoreo industrial en tiempo real para líneas de producción con visión artificial. Visualiza métricas de producción, calcula KPIs (OEE: Disponibilidad, Rendimiento, Calidad) y gestiona paradas de línea de forma automatizada y escalable.

**Versión:** 2.0.0  
**Última actualización:** 13 Febrero 2026  
**Python:** 3.12+

---

## 🏗️ Arquitectura del Sistema

Arquitectura **dual-server** con separación clara de responsabilidades:

| Componente | Framework | Puerto | Rol |
|------------|-----------|--------|-----|
| **API de Datos** | FastAPI | 8000 | REST API async, procesamiento de datos, cálculo de métricas |
| **Frontend SSR** | Flask | 5000 | Renderizado de templates, autenticación, sesiones |

Ambos servidores comparten el mismo codebase Python y módulo de base de datos, pero se ejecutan como procesos independientes.

### Multi-Tenancy con Bases de Datos Aisladas

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENTE (Browser)                         │
│          Alpine.js 3.13 · Chart.js 4.4 · Tailwind CSS           │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FLASK (Puerto 5000)                          │
│     Session-based Auth · Jinja2 SSR · Proxy a FastAPI            │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP interno (httpx)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FASTAPI (Puerto 8000)                         │
│              REST API · CORS · MetadataCache                     │
│    ┌───────────────┬──────────────┬────────────────┐            │
│    │ /api/v1/      │ /api/v1/     │ /api/v1/       │            │
│    │ dashboard/    │ filters/     │ system/        │            │
│    │ widgets/      │ layout/      │                │            │
│    └───────┬───────┴──────┬───────┴────────┬───────┘            │
│            │              │                │                     │
│    ┌───────▼──────────────▼────────────────▼───────┐            │
│    │           SERVICE LAYER                       │            │
│    │  DashboardDataService · LayoutService         │            │
│    │  FilterResolver · Processors (KPI/Charts)     │            │
│    │  DataAggregator · DowntimeCalculator           │            │
│    └──────────────────────┬────────────────────────┘            │
│                           │                                      │
│    ┌──────────────────────▼────────────────────────┐            │
│    │         METADATA CACHE (In-Memory)            │            │
│    │  Líneas · Áreas · Productos · Turnos          │            │
│    │  Filtros · Fallas · Incidentes · Widgets      │            │
│    └──────────────────────┬────────────────────────┘            │
└───────────────────────────┼─────────────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            ▼                               ▼
┌───────────────────┐           ┌───────────────────────┐
│  camet_global     │           │ db_client_{tenant}    │
│  ─────────────    │           │ ───────────────────── │
│  tenant           │           │ production_line       │
│  user             │           │ area                  │
│  widget_catalog   │           │ product / shift       │
│  dashboard_templ. │           │ filter / failure      │
│  user_login       │           │ detection_line_X (*)  │
│  audit_log        │           │ downtime_events_X (*) │
└───────────────────┘           └───────────────────────┘
                                (*) tablas dinámicas por línea
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
| **Pydantic** | v2 | Validación de datos, settings |
| **Pandas** | 2.2+ | Procesamiento y enriquecimiento de datos |
| **Uvicorn** | 0.29.0 | ASGI server para FastAPI |

### Frontend (CDN, zero build step)
| Tecnología | Versión | Uso |
|------------|---------|-----|
| **Alpine.js** | 3.13.3 | Reactividad client-side |
| **Chart.js** | 4.4.0 | Gráficos interactivos |
| **chartjs-plugin-zoom** | 2.0.1 | Zoom/pan en gráficos |
| **chartjs-plugin-annotation** | 3.0.1 | Marcas de paradas |
| **Hammer.js** | 2.0.8 | Soporte touch para zoom |
| **HTMX** | 1.9.10 | Actualizaciones parciales |
| **Tailwind CSS** | CDN | Estilos utility-first |

### Base de Datos
| Tecnología | Uso |
|------------|-----|
| **MySQL 8.0+** | Motor principal |
| **NullPool** | Compatibilidad con hosting compartido |
| **Tablas dinámicas** | `detection_line_{name}`, `downtime_events_{name}` por línea |

### Seguridad
| Tecnología | Uso |
|------------|-----|
| **Argon2** | Hashing de contraseñas (time=2, memory=64KB) |
| **Flask Sessions** | Autenticación server-side |
| **CORS** | Restricción de orígenes (localhost) |
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

JWT_SECRET_KEY=your-jwt-secret
JWT_ALGORITHM=HS256
```

### Ejecutar
```bash
# Ambos servidores simultáneamente
python run.py

# Solo API FastAPI (puerto 8000)
python run.py api

# Solo Frontend Flask (puerto 5000)
python run.py web
```

### Acceso
- **Dashboard:** http://127.0.0.1:5000
- **API Docs:** http://127.0.0.1:8000/api/docs (solo en `DEBUG=True`)
- **Credenciales de prueba:** `admin` / `admin123`

---

## ✅ Estado Actual de Funcionalidades

### Implementado y Funcional
- [x] Arquitectura multi-tenant con aislamiento de datos
- [x] Autenticación session-based con Argon2 + auditoría
- [x] MetadataCache in-memory thread-safe
- [x] Pipeline de datos unificado (single POST → all widgets)
- [x] 13 tipos de widgets (7 KPIs, 4 charts, scatter, tables, ranking)
- [x] 6 tipos de filtros dinámicos con cascade
- [x] Agrupación de líneas ("Todas las líneas" + grupos custom)
- [x] Detección automática de paradas por gap analysis
- [x] Cálculo completo de OEE (Disponibilidad × Rendimiento × Calidad)
- [x] Zoom/pan interactivo en gráficos con reset
- [x] Anotaciones de paradas en gráficos de línea
- [x] Modo multi-línea (oculta métricas de paradas)
- [x] Tema oscuro por defecto con toggle
- [x] Layout responsivo CSS Grid 4 columnas

### En Requirements pero No Implementado
- [ ] JWT para API (`pyjwt` instalado, settings configurados)
- [ ] APScheduler para tasks en background
- [ ] Alembic migrations
- [ ] Rate limiting con slowapi
- [ ] CSRF con Flask-WTF

---

## 📄 Documentos Relacionados

- [Documentation.md](Documentation.md) — Documentación técnica completa
- [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) — Resumen de implementación
- [ARCHITECTURE_REFACTOR.md](ARCHITECTURE_REFACTOR.md) — Principios SRP/DRY
- [ARCHITECTURE_DIAGRAMS.md](ARCHITECTURE_DIAGRAMS.md) — Diagramas de arquitectura
- [TODO.md](TODO.md) — Roadmap y tareas pendientes
- [Planificacion.md](Planificacion.md) — Planificación original por fases

---

**Proyecto propietario — Camet Robótica. Todos los derechos reservados.**
