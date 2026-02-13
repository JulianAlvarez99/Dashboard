# TODO & Roadmap — Camet Analytics Dashboard

Tareas pendientes organizadas por prioridad. Comparado contra la planificación original (`Planificacion.md`).

**Última actualización:** 13 Febrero 2026

---

## Prioridad Crítica

Funcionalidades que deberían implementarse antes de producción.

### Seguridad de la API (Phase 8)
- [ ] **JWT Authentication para FastAPI** — La API está completamente abierta. Requiere:
  - Crear middleware/dependency que valide JWT en cada request
  - Endpoints: `POST /auth/token`, `POST /auth/refresh`, `GET /auth/me`
  - Usar `pyjwt` (ya instalado, settings `JWT_SECRET_KEY`/`JWT_ALGORITHM` configurados)
  - Inyectar tenant_id del token en las queries
- [ ] **CSRF Protection** — `flask-wtf` instalado pero no activado
  - Agregar `CSRFProtect(app)` en Flask
  - Incluir `csrf_token()` en formularios
- [ ] **Security Headers** — No hay middleware de headers
  - X-Frame-Options: DENY
  - Content-Security-Policy
  - X-Content-Type-Options: nosniff
  - Strict-Transport-Security (cuando HTTPS)
- [ ] **Rate Limiting** — `slowapi` instalado pero no activado
  - Aplicar a `/auth/login` (anti-brute-force)
  - Aplicar a `/api/v1/*` (anti-abuse)
- [ ] **Permisos por rol** — RBAC definido (5 roles) pero no aplicado
  - Los endpoints no verifican `session["user"]["role"]`
  - Crear decorador `@role_required("ADMIN", "MANAGER")`
  - Restringir cache/refresh a ADMIN+

### Bug Conocido
- [ ] **DatabaseManager.get_tenant_engine_by_name()** — Referencia `settings.DB_USER` / `settings.DB_PASSWORD` que no existen. Cambiar a `settings.TENANT_DB_USER` / `settings.TENANT_DB_PASSWORD`

---

## Prioridad Alta

Funcionalidades importantes para estabilidad y mantenimiento.

### Tests (Nunca creados)
- [ ] Crear directorio `tests/`
- [ ] Tests unitarios para procesadores KPI (especialmente OEE)
- [ ] Tests para `downtime_calculator.py` (edge cases: overnight, threshold exacto)
- [ ] Tests para `FilterResolver` y `FilterFactory`
- [ ] Tests de integración para el pipeline completo
- [ ] Tests de seguridad (SQL injection, XSS)
- [ ] Configurar `pytest` + `pytest-asyncio`

### Migrations
- [ ] Configurar Alembic (`alembic` ya instalado)
- [ ] Crear migrations iniciales para `camet_global` y `db_client_*`
- [ ] Script de creación de tablas dinámicas (`detection_line_X`, `downtime_events_X`)

### Scripts de Deploy
- [ ] `scripts/init_db.py` — Inicialización de DB con seed data
- [ ] `scripts/setup_production.sh` — Setup de producción
- [ ] `scripts/backup_db.sh` — Backups automatizados
- [ ] `passenger_wsgi.py` para cPanel

---

## Prioridad Media

Mejoras funcionales para usuarios.

### CRUD de Configuración (Phase 2)
- [ ] Endpoints para gestionar `production_line` (GET/POST/PUT/DELETE)
- [ ] Endpoints para gestionar `area`, `product`, `shift`
- [ ] Invalidación de cache automática al modificar datos
- [ ] UI de administración para gestión de líneas/áreas/productos

### Downtime Automático (Phase 4)
- [ ] Background task con APScheduler para calcular downtimes cada 15 min
- [ ] Guardar resultados calculados en `downtime_events_X`
- [ ] Endpoint para recálculo manual

### Reportes y Exportación
- [ ] Exportar dashboard a PDF
- [ ] Exportar datos a Excel/CSV
- [ ] Reportes programados por email
- [ ] Comparación entre períodos

### Mejoras de UI
- [ ] HTMX para actualizaciones parciales (sidebar, filtros cascade)
- [ ] Lazy loading de widgets
- [ ] Indicadores de tendencia (trend) en KPIs
- [ ] Modo claro/oscuro persistente (actualmente solo oscuro)

---

## Prioridad Baja

Features avanzados para el futuro.

### Alertas y Notificaciones
- [ ] Sistema de alertas por email
- [ ] Webhooks para eventos de downtime
- [ ] Alertas de parada prolongada
- [ ] Dashboard de alertas activas

### Real-Time
- [ ] WebSocket para actualizaciones en vivo
- [ ] Server-Sent Events como alternativa
- [ ] Auto-refresh configurable por widget

### Performance Avanzado
- [ ] Particionamiento automático de tablas de detección (mensual)
- [ ] Script de optimización de índices
- [ ] Redis como cache layer (reemplazar in-memory)
- [ ] Connection pool tuning (reemplazar NullPool en producción dedicada)
- [ ] Middleware de monitoreo (X-Process-Time, slow query logging)

### Multi-Planta
- [ ] Segmentación por planta
- [ ] Dashboards comparativos entre plantas
- [ ] Switch de tenant dinámico

### Otros
- [ ] 2FA (TOTP / SMS / códigos de recuperación)
- [ ] Multi-idioma (i18n)
- [ ] API pública con API keys
- [ ] Machine learning: predicción de paradas, detección de anomalías
- [ ] Archival de datos históricos (retención, compresión, cold storage)

---

## Paquetes Instalados sin Usar

Estos paquetes están en `requirements.txt` pero no tienen código que los utilice:

| Paquete | Uso previsto | Acción sugerida |
|---------|-------------|-----------------|
| `pyjwt` | JWT auth para API | Implementar JWT middleware |
| `slowapi` | Rate limiting | Activar en endpoints |
| `apscheduler` | Background tasks | Implementar downtime auto-calc |
| `flask-wtf` | CSRF protection | Activar CSRFProtect |
| `alembic` | DB migrations | Configurar y crear migrations |
| `bleach` | XSS sanitization | Aplicar en inputs de usuario |
| `cryptography` | Encrypt utilities | Evaluar necesidad |

---

## Directorios Planeados que No Existen

| Directorio | Propósito | Prioridad |
|------------|-----------|-----------|
| `tests/` | Tests unitarios e integración | Alta |
| `scripts/` | Setup, backup, deploy | Alta |
| `app/middleware/` | JWT, rate limit, headers, audit | Crítica |
| `migrations/` | Alembic DB migrations | Alta |
| `app/utils/` | Utilities (partition manager, etc.) | Media |
| `app/schemas/` | Pydantic schemas dedicados | Baja |

---

_TODO actualizado. Para detalles de la planificación original, ver [Planificacion.md](Planificacion.md)._
