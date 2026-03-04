# TODO & Roadmap — Camet Analytics Dashboard

Tareas pendientes por prioridad. Estado al **4 Marzo 2026**.

---

## 🔴 Prioridad Crítica

### Seguridad de la API

- [X] **JWT Authentication para FastAPI**
  - La API está completamente abierta (sin auth).
  - `pyjwt` ya instalado. Campos `JWT_SECRET_KEY` / `JWT_ALGORITHM` en Settings.
  - Crear dependency `require_tenant` que valide JWT en cada request.
  - Endpoints: `POST /auth/token`, `POST /auth/refresh`
  - Inyectar `tenant_id` del token en `TenantContext`

- [X] **CSRF Protection**
  - `flask-wtf` instalado pero no activado.
  - Agregar `CSRFProtect(app)` en `flask_app.py`
  - Incluir `csrf_token()` en formulario de login

- [X] **Rate Limiting**
  - `slowapi` instalado pero no activado.
  - Aplicar en `/auth/login` (anti-brute-force)
  - Aplicar en `/api/v1/*` (anti-abuse)

- [X] **Security Headers**
  - No hay middleware de headers HTTP.
  - `X-Frame-Options: DENY`
  - `Content-Security-Policy`
  - `X-Content-Type-Options: nosniff`

- [ ] **RBAC Enforcement en Endpoints**
  - Los 3 roles están definidos: ADMIN, MANAGER, OPERATOR
  - Ningún endpoint verifica el rol del usuario actualmente.
  - Crear dependency `@role_required("ADMIN")` en FastAPI
  - Crear decorador Flask `@role_required("MANAGER")` para rutas SSR
  - Restringir `/system/cache/refresh` a ADMIN+

---

## 🟠 Prioridad Alta

### Suite de Tests (29 tests pasando)

- [X] Crear directorio `tests/` con estructura básica — vive en `tests/unit/`
- [X] Tests unitarios para `_compute_oee()` (casos límite OEE)
- [X] Tests para `downtime_calculator.py` (gap analysis edge cases)
- [X] Tests para `FilterEngine.validate_input()`
- [X] Tests para `QueryBuilder` (queries con particiones, filtros, cursores)
- [X] Configurar `pytest` + `pytest-asyncio`
- [ ] Tests de integración para el pipeline completo (`DashboardOrchestrator.execute()`)
- [ ] `WidgetEngine` coverage (auto-discovery, widget desconocido)

### Migrations

- [ ] Configurar **Alembic** (instalado, no configurado)
- [ ] Migration inicial para `camet_global`
- [ ] Migration inicial para esquema base de `db_client_*`
- [ ] Script para crear tablas dinámicas (`detection_line_X`, `downtime_events_X`)

### Scripts de Deploy

- [X] `scripts/init_db.py` — inicialización + seed de datos
- [X] `scripts/setup_production.sh` — setup de entorno producción
- [X] `passenger_wsgi.py` para cPanel deployment

### Bug conocido

- [ ] `DatabaseManager.get_tenant_engine_by_name()` referencia `settings.DB_USER` / `settings.DB_PASSWORD` que no existen. Cambiar a `settings.TENANT_DB_USER` / `settings.TENANT_DB_PASSWORD`.

---

## 🟡 Prioridad Media

### Próximos Pasos Funcionales

- [ ] **Downtime Automático con APScheduler**
  - `apscheduler` instalado pero no activado.
  - Background task cada 15 min: calcula gap downtime y persiste en `downtime_events_X`
  - Endpoint manual: `POST /api/v1/system/downtime/recalculate`

- [ ] **CRUD de Configuración**
  - Endpoints para gestionar `production_line` (GET/POST/PUT/DELETE)
  - Endpoints para gestionar `area`, `product`, `shift`
  - Invalidación de `MetadataCache` al modificar

- [ ] **Nuevos Widgets** (fácil de agregar gracias a auto-discovery)
  - Widget de tendencia/sparklines
  - Mapa de calor de producción (heatmap por hora × día)
  - Widget de alertas activas
  - Comparador de períodos (semana anterior vs actual)

- [ ] **Nuevos Filtros**
  - `FailureTypeFilter` — por tipo de falla
  - `OperatorFilter` — filtrar por operario
  - `PlantFilter` — preparación para multi-planta

- [ ] **Exportación**
  - Exportar dashboard a PDF
  - Exportar datos a Excel/CSV desde endpoints existentes de raw_data
  - Aprovechar `export.py` ya creado en `services/data/`

- [ ] **Persistencia del Layout por Usuario**
  - Guardar preferencias en `dashboard_template` por usuario (no solo por rol)
  - Permitir drag & drop en el dashboard

### UI/UX

- [ ] Modo claro persistente (toggle guarda en localStorage)
- [ ] Lazy loading de widgets (cargar por tab, no todo a la vez)
- [ ] Indicadores de tendencia (▲▼) en KPIs
- [ ] Actualización automática configurable (auto-refresh cada N minutos)
- [ ] `new_app/static/js/modules/` — modularizar JavaScript

---

## 🟢 Prioridad Baja

### Alertas y Notificaciones

- [ ] Sistema de alertas por email
- [ ] Webhooks para eventos de downtime
- [ ] Alertas de parada prolongada (>X minutos)
- [ ] Panel de alertas activas en el dashboard

### Real-Time

- [ ] WebSocket o Server-Sent Events para actualizaciones en vivo
- [ ] Remplazar auto-refresh manual por push del servidor

### Performance Avanzado

- [ ] Redis como cache layer (reemplazar in-memory para multi-proceso)
- [ ] `connection pool` tuning (reemplazar NullPool en hosting dedicado)
- [ ] Middleware `X-Process-Time` para monitoreo de latencia
- [ ] Particionamiento automático mensual (actualmente manual con `partition_manager.py`)

### Multi-Planta

- [ ] Segmentación por planta (campo `plant_id` en modelos)
- [ ] Dashboards comparativos entre plantas
- [ ] Switch de tenant dinámico desde la UI

### Seguridad Avanzada

- [ ] 2FA (TOTP / códigos de recuperación)
- [ ] Sesiones con expiración configurable
- [ ] `bleach` para sanitización de inputs de usuario (instalado, no usado)
- [ ] Audit log más granular (qué filtros aplicó cada usuario)

### Calidad de Código

- [ ] Llenar `new_app/utils/` con utilidades extraídas de `helpers.py`
- [ ] Implementar módulos JS en `new_app/static/js/modules/`
- [ ] Typing completa (mypy / Pyright strict)
- [ ] Pre-commit hooks (black, ruff, isort)

---

## 📦 Paquetes Instalados Sin Usar

| Paquete | Uso Previsto | Acción |
|---------|-------------|--------|
| `pyjwt` | JWT auth para FastAPI | Implementar JWT middleware |
| `apscheduler` | Background tasks | Activar downtime auto-calc |
| `flask-wtf` | CSRF protection | Activar `CSRFProtect(app)` |
| `alembic` | DB migrations | Inicializar con `alembic init` |
| `bleach` | XSS sanitization | Aplicar en inputs de usuario |
| `cryptography` | Crypto utilities | Evaluar necesidad real |

> `slowapi` → ya no se usa; rate limiting implementado con `RateLimitMiddleware` custom.

---

## 📂 Directorios Vacíos / Faltantes

| Directorio | Estado | Propósito |
|------------|--------|-----------|
| `new_app/utils/` | Existe | Utilidades compartidas |
| `new_app/static/js/modules/` | Existe pero vacío | Módulos JS |
| `tests/unit/` | ✅ Existe, 29 tests | Tests unitarios |
| `migrations/` | Existe (Alembic esqueleto) | Alembic migrations |

---

_Última actualización: 4 Marzo 2026. Ver [README.md](README.md) para estado general._