# Plan: Code Review & cPanel Deployment — `new_app/` (v2)

Revisión exhaustiva de `new_app/`. El plan está ordenado por prioridad. Se incorporan tres ajustes respecto a v1: (1) el problema de MetadataCache single-tenant se descarta porque cada cliente tendrá su propia instancia de app, (2) se implementan escrituras reales al `AuditLog` en login/logout, y (3) se agrega log de queries de usuario contra la tabla `user_query` existente en DB.

---

## NOTAS DE CONTEXTO DEL ESQUEMA DE DB

### Tabla `audit_log` (real en DB)
Columnas: `log_id (bigint PK)`, `user_id (bigint NOT NULL FK)`, `action (varchar 50)`, `ip_address (varchar 45)`, `details (longtext/JSON)`, `created_at (timestamp)`.

> **Limitación:** `user_id` es `NOT NULL` en la DB real. Para loguear intentos de login fallidos (donde el user no existe), se requiere una migración ALTER TABLE para hacerlo nullable, O usar un `user_id` convencional como `0` para failures. Decidir antes de implementar el Paso 9.

### Tabla `user_query` (real en DB - ya existe)
Columnas: `query_id (int PK)`, `user_id (bigint FK)`, `username (varchar 50)`, `slq_query (text)` ← *typo en DB, mantener tal cual*, `query_parameters (text)`, `start_date (date)`, `start_time (time)`, `end_date (date)`, `end_time (time)`, `line (varchar 20)`, `interval_type (varchar 20)`, `created_at (timestamp)`.

> La tabla `user_query` ya existe en la DB con estructura específica. El modelo ORM y el servicio deben mapear exactamente a estas columnas. No crear una tabla nueva — usar la existente. El campo `slq_query` tiene un typo en la DB (`slq` en lugar de `sql`); mantenerlo exactamente así para no necesitar migración.

---

## PARTE 1 — SEGURIDAD 🔴

**Paso 1 — Validar que los secrets nunca sean vacíos** en `new_app/core/config.py`

Agregar `@validator` de Pydantic sobre `SECRET_KEY`, `FLASK_SECRET_KEY` y `JWT_SECRET_KEY`. Si alguno es vacío en startup, la app lanza `ValueError` y se niega a arrancar.

**Paso 2 — Autenticar endpoints sensibles de FastAPI** en `new_app/api/v1/system.py`

`POST /cache/load/{db_name}` y `POST /cache/refresh` son accesibles sin auth. Implementar validación de un header `X-Internal-Key` contra `settings.API_INTERNAL_KEY` en un `Depends()` llamado `require_internal_key`. Agregar este Depends a ambos endpoints.

**Paso 3 — Corregir el fallback `return 1` del tenant_id** en `new_app/api/v1/dashboard.py`

`_resolve_tenant_id()` devuelve `1` si no se pasa `tenant_id` → cualquier request sin ese campo produce que el servidor devuelva datos del tenant 1. Cambiar a `raise HTTPException(400, "tenant_id is required")`.

**Paso 4 — Protección CSRF en login** en `new_app/routes/auth.py`

El formulario de login no tiene protección CSRF. Agregar `Flask-WTF` al `requirements.txt` e inicializar `CSRFProtect(app)` en `new_app/flask_app.py`. Agregar `{{ csrf_token() }}` al template `new_app/templates/auth/login.html`.

**Paso 5 — Corregir CORS en producción** en `new_app/main.py`

Mover `allow_origins` a `settings.CORS_ALLOWED_ORIGINS` (env var, lista separada por comas). Cambiar `allow_methods=["*"]` a `["GET", "POST"]`. Eliminar los hardcoded `localhost`.

**Paso 6 — Rate limiting en login** en `new_app/routes/auth.py`

`RATE_LIMIT_PER_MINUTE` ya existe en config pero nunca se aplica. Agregar `Flask-Limiter` al `requirements.txt`, inicializarlo en el factory de Flask, y aplicar `@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE} per minute")` al handler de login.

**Paso 7 — Session fixation en login** en `new_app/routes/auth.py`

Llamar `session.clear()` inmediatamente antes de `session["user"] = user_info` para limpiar cualquier sesión pre-autenticación y evitar session fixation.

---

## PARTE 2 — AUDIT LOG: Escrituras reales 🆕

El modelo `AuditLog` en `new_app/models/global_models.py` existe con los campos `user_id`, `action`, `ip_address`, `details (JSON)`, `created_at` — pero **nunca se escribe**. `UserLogin` ya registra login/logout_at. El plan es usar `AuditLog` para eventos de **seguridad** (login exitoso, login fallido, logout).

**Paso 8 — Crear `AuditLogService`** como nuevo archivo `new_app/services/audit/audit_service.py`

Responsabilidad única (SRP): escribir al `audit_log`. Exponer estas funciones:

- `log_login_success(db, user_id, ip, user_agent, tenant_id)` → `action="LOGIN_SUCCESS"`
- `log_login_failure(db, user_id_or_none, username, ip, reason)` → `action="LOGIN_FAILURE"` (ver nota sobre `user_id NOT NULL` más abajo)
- `log_logout(db, user_id, ip)` → `action="LOGOUT"`

El campo `details` (JSON/longtext) almacena metadata relevante: `{"username": ..., "tenant_id": ..., "user_agent": ...}` en login; `{"reason": "bad_password" | "inactive_tenant", "attempted_username": ...}` en failures.

**Paso 9 — Decisión: `audit_log.user_id NOT NULL`** en `new_app/models/global_models.py`

La DB real tiene `user_id bigint NOT NULL`. Para loguear login fallidos donde el usuario no existe en DB, elegir UNA de estas opciones antes de implementar:

- **Opción A (sin migración):** Usar `user_id = 0` como convención para "usuario desconocido". Documentar en el modelo.
- **Opción B (con migración):** `ALTER TABLE audit_log MODIFY user_id bigint(20) NULL;` y cambiar el modelo a `Mapped[Optional[int]]`. También agregar campo `username: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)` para registrar el username intentado.

**Paso 10 — Integrar `AuditLogService` en las rutas** en `new_app/routes/auth.py`

En el handler de login:
- En el bloque de éxito: llamar `audit_service.log_login_success(db, ...)`
- En el bloque de fallo (`user_info is None`): llamar `audit_service.log_login_failure(db, ...)`
- En logout: llamar `audit_service.log_logout(db, ...)`

Estas llamadas reemplazan los `print()` actuales de audit. El bloque `try/except` de cada escritura debe loguear al `logger` (no `print`) sin propagar la excepción — un fallo de audit no debe interrumpir el login del usuario.

---

## PARTE 3 — USER QUERY LOG: Mapear a tabla existente 🆕

La tabla `user_query` ya existe en la DB global con estructura propia. El ORM model y el servicio deben ajustarse a ella exactamente.

**Paso 11 — Crear el modelo `UserQuery`** en `new_app/models/global_models.py`

Agregar el modelo ORM que mapee exactamente a la tabla existente:

```python
class UserQuery(GlobalBase):
    """User query activity log. Maps to existing 'user_query' table."""
    __tablename__ = "user_query"

    query_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.user_id"), nullable=False)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    slq_query: Mapped[str] = mapped_column(Text, nullable=False)   # typo en DB — mantener
    query_parameters: Mapped[str] = mapped_column(Text, nullable=False)  # JSON serializado como str
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    line: Mapped[str] = mapped_column(String(20), nullable=False)
    interval_type: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
```

> **Nota sobre `slq_query`:** El campo tiene un typo en la DB (`slq` en vez de `sql`). El ORM debe usar `slq_query` verbatim para no necesitar una migración. Agregar un comentario en el modelo explicando el typo para que futuros devs no lo "corrijan".

> **Nota sobre `query_parameters`:** La DB define este campo como `text` (no JSON nativo). Serializar el dict de parámetros con `json.dumps()` antes de insertar y deserializar con `json.loads()` al leer.

> **Nota sobre fechas/horas:** La tabla tiene `start_date`, `start_time`, `end_date`, `end_time` como campos separados (Date/Time). El servicio debe extraerlos del dict `daterange` del request antes de insertar.

**Paso 12 — Crear `QueryLogService`** como `new_app/services/audit/query_log_service.py`

Responsabilidad única: escribir al `user_query`. Exponer:

```python
async def log_query(
    db_name: str,
    user_id: int,
    username: str,
    sql_text: str,         # texto descriptivo de la query o template
    filters: dict,         # dict completo de filtros usados
    line: str,             # line_id o "all"
    interval_type: str,
) -> None:
```

La función extrae `start_date`, `start_time`, `end_date`, `end_time` del dict `filters["daterange"]`. Serializa `filters` como JSON string para `query_parameters`. Escribe a la DB global usando `db_manager.get_global_session_sync()`.

La escritura debe ser **fire-and-forget**: usar `asyncio.create_task()` o lanzar en un thread para no añadir latencia al response del dashboard. Si falla, loguear el error al `logger` sin propagar.

**Paso 13 — Hook en el endpoint del dashboard** en `new_app/api/v1/dashboard.py`

Al final del handler `POST /dashboard/data`, después de que el orquestador retorna, lanzar `query_log_service.log_query(...)` como fire-and-forget. Usar `time.perf_counter()` al inicio y fin del handler para tener contexto de timing (aunque la tabla actual no tiene `duration_ms`, esto puede loguearse en el `query_parameters` JSON como campo adicional).

**Paso 14 — Crear `new_app/services/audit/__init__.py`**

Exportar `audit_service` y `query_log_service` para facilitar imports.

---

## PARTE 4 — ARQUITECTURA SRP/DRY 🟠

**Paso 15 — Unificar CamelCase→snake_case** en nuevo módulo `new_app/utils/naming.py`

Existe en `new_app/services/widgets/engine.py` (versión loop) y `new_app/services/filters/engine.py` (versión regex). Crear `camel_to_snake(name: str) -> str` usando la versión regex y reemplazar ambas implementaciones.

**Paso 16 — Unificar request → cleaned filter dict** en nuevo archivo `new_app/utils/request_helpers.py`

`_extract_user_params` en `new_app/api/v1/dashboard.py` y `_build_cleaned` en `new_app/api/v1/detections.py` son lógicamente idénticas. Mover a `build_filter_dict(request_model) -> dict` y reemplazar ambos usos.

**Paso 17 — Eliminar checks manuales de cache en filters.py** en `new_app/api/v1/filters.py`

El patrón `if not metadata_cache.is_loaded: raise HTTPException(503)` aparece 6 veces. Ya existe `Depends(require_cache)` en `new_app/api/v1/dependencies.py`. Agregar el Depends a cada ruta y eliminar los 6 checks manuales.

**Paso 18 — Refactorizar las 4 responsabilidades del login handler** en `new_app/routes/auth.py`

Extraer a funciones privadas: `_authenticate(db, username, password)`, `_build_session(user_info)`, y dejar las escrituras de audit al `AuditLogService` del Paso 8. El handler queda como orquestador delgado que llama a estas funciones.

**Paso 19 — Desacoplar cache warm-up del login** en `new_app/routes/auth.py`

La llamada `httpx.post(api_url, timeout=15.0)` bloquea el thread Flask hasta 15s. Mover a un `threading.Thread(daemon=True, target=_warmup_cache)` que se lanza después del commit sin bloquear el response de login.

**Paso 20 — Limpiar código muerto**

- `new_app/core/database.py`: `get_global_db` y `get_tenant_db` como `Depends()` nunca usados → eliminar o documentar como "reservado para uso futuro".
- `new_app/services/broker/data_broker.py` y `new_app/services/orchestrator/pipeline.py`: `DataBroker` bypaseado por el pipeline → agregar comentario prominente `# NOT ACTIVE — planned for Phase 2`.

---

## PARTE 5 — PERFORMANCE 🟡

**Paso 21 — Vectorizar enrichment.py** en `new_app/services/data/enrichment.py`

8 ocurrencias de `df["col"] = df["id"].map(lambda x: cache.get(x, {}).get("field", default))`. Refactorizar a helper `_map_column(df, id_col, lookup_dict, field, default)` y reemplazar con `df["id"].map({id: data[field] for id, data in lookup.items()})`. Diferencia ~5–10× más rápido a 500K filas.

**Paso 22 — Paralelizar count queries** en `new_app/services/data/detection_service.py`

`get_detection_count` itera `line_ids` secuencialmente con N queries seriales. Cambiar a `asyncio.gather(*[_count_for_line(lid) for lid in line_ids])`.

**Paso 23 — Cachear la resolución del layout** en `new_app/services/config/layout_service.py`

`get_resolved_layout()` hace una query a `camet_global` en cada page load. Mover esta resolución al `MetadataCache` (cargada una vez en login) en lugar de on-demand por request.

**Paso 24 — Cachear instancias de filtros en FilterEngine** en `new_app/services/filters/engine.py`

`get_all()` reinstancia objetos filtro 3–4 veces por request. Agregar `_cached_instances: dict | None = None` como atributo de clase. Los filtros son stateless, por lo que el cache es seguro.

**Paso 25 — Reverse-map en WidgetEngine** en `new_app/services/widgets/engine.py`

`_resolve_catalog_info` hace scan lineal por widget ejecutado. Construir `_class_to_id: Dict[str, int]` en `__init__` del engine, una sola vez.

**Paso 26 — Límite configurable de export rows** en `new_app/services/data/detection_repository.py`

`MAX_TOTAL_ROWS=2_000_000` puede causar OOM en cPanel (256MB típico). Leer de `settings.MAX_EXPORT_ROWS` con default conservador de `100_000`.

---

## PARTE 6 — MANEJO DE ERRORES Y LOGGING 🟡

**Paso 27 — Reemplazar todos los `print()` por `logger`**

Archivos afectados: `new_app/main.py`, `new_app/core/auth.py`, `new_app/routes/auth.py`. En cada módulo: `logger = logging.getLogger(__name__)`.

**Paso 28 — Handler global de excepciones en FastAPI** en `new_app/main.py`

Registrar `@app.exception_handler(Exception)` que loguee el traceback completo y devuelva `{"error": "Internal server error"}` en lugar del traceback raw de FastAPI.

**Paso 29 — Diferenciar excepciones en auth** en `new_app/core/auth.py`

El `except Exception as exc` actual swallows todo. Separar `sqlalchemy.exc.OperationalError` (re-raise como `DatabaseUnavailableError`) de `PasswordVerifyMismatch` (return `None`).

**Paso 30 — Propagar errores parciales en repository** en `new_app/services/data/detection_repository.py`

El `except Exception: break` devuelve datos parciales como si fueran completos. El `WidgetResult` debe incluir `is_truncated: bool` y `error_message: Optional[str]` para que el frontend informe al usuario "Datos incompletos".

**Paso 31 — Corregir `datetime.utcnow()` deprecado** en `new_app/routes/auth.py`

Reemplazar por `datetime.now(timezone.utc)`.

---

## PARTE 7 — EXTENSIBILIDAD 🟢

**Paso 32 — Validación de layout en startup** en `new_app/config/widget_layout.py`

Agregar `validate_layout_consistency()` llamada desde el lifespan de FastAPI. Verifica que cada clave de `WIDGET_LAYOUT` corresponda a una clase importable en `services/widgets/types/`. Fallo en startup con mensaje claro si hay discrepancia.

**Paso 33 — Hacer `SHOW_OEE_TAB` configurable desde env** en `new_app/config/widget_layout.py`

Leer de `settings.SHOW_OEE_TAB` (env var `SHOW_OEE_TAB=true/false`) en lugar de hardcoded `False`.

**Paso 34 — Eliminar la capa redundante en DateRangeFilter**

`services/filters/types/date_range_filter.py` es un re-export de `daterange.py`. Consolidar en un único archivo.

---

## PARTE 8 — DOCUMENTACIÓN FALTANTE 📄

**Paso 35 — Actualizar `Documentation/WIDGETS_AND_FILTERS.md`**

El flujo correcto completo para agregar un widget incluye el paso que actualmente falta: actualizar `dashboard_template.layout_config` en la DB global para el tenant+role deseados.

Flujo completo documentado:
1. Crear `services/widgets/types/mi_widget.py` con la clase
2. Insertar fila en `widget_catalog` (global DB)
3. Agregar entrada en `config/widget_layout.py`
4. Actualizar `dashboard_template.layout_config` JSON en global DB para el tenant+role
5. Si tiene un `chart_type` nuevo → actualizar `CHART_TYPE_MAP` en `dashboard-app.js`
6. Reload de cache (`POST /api/v1/system/cache/refresh`)

**Paso 36 — Crear `Documentation/ARCHITECTURE.md`**

Diseño dual-proceso Flask (5000) + FastAPI (8000), startup order, flujo de request end-to-end, y comunicación inter-proceso.

**Paso 37 — Crear `Documentation/DEPLOYMENT_CPANEL.md`** (nuevo)

Ver Parte 9.

---

## PARTE 9 — DEPLOYMENT EN CPANEL

### Arquitectura de deployment

La app tiene dos componentes:
- **Flask** (WSGI) → cPanel con Passenger lo maneja nativamente
- **FastAPI** (ASGI) → requiere `uvicorn` como proceso separado

Sin SSH, la única opción viable es **Opción A (proceso único)**. Con SSH disponible, **Opción B (dual proceso)** mantiene la arquitectura actual.

**Opción A — Proceso único (recomendada para shared cPanel sin SSH):**
Flask importa los servicios de FastAPI directamente (sin HTTP inter-proceso). Se elimina la llamada `httpx.post()` del login. El `passenger_wsgi.py` expone solo Flask.

**Opción B — Dual proceso (requiere SSH):**
`passenger_wsgi.py` para Flask + `startup.sh` que arranca `uvicorn new_app.main:app --port 8000 --no-access-log` con `nohup`.

**Paso 38 — Crear `passenger_wsgi.py`** en la raíz del proyecto

```python
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("ENV", "production")
from new_app.flask_app import flask_app as application
```

**Paso 39 — Crear `.env.example`** (commiteado como template; el `.env` real nunca se commitea)

Todas las variables a configurar en cPanel → "Python App" → "Environment Variables":

| Variable | Descripción | Ejemplo |
|---|---|---|
| `ENV` | Entorno | `production` |
| `FLASK_SECRET_KEY` | Secreto sesiones Flask (≥32 chars) | `<random-32-chars>` |
| `SECRET_KEY` | Secreto general | `<random-32-chars>` |
| `JWT_SECRET_KEY` | Secreto JWT | `<random-32-chars>` |
| `GLOBAL_DB_HOST` | Host MySQL global | `localhost` |
| `GLOBAL_DB_PORT` | Puerto MySQL | `3306` |
| `GLOBAL_DB_NAME` | DB global | `camet_global` |
| `GLOBAL_DB_USER` | Usuario DB (no root) | `camet_user` |
| `GLOBAL_DB_PASSWORD` | Password DB global | `<seguro>` |
| `TENANT_DB_HOST` | Host MySQL tenants | `localhost` |
| `TENANT_DB_USER` | Usuario DB tenants | `tenant_user` |
| `TENANT_DB_PASSWORD` | Password DB tenants | `<seguro>` |
| `TENANT_DB_PORT` | Puerto tenant DB | `3306` |
| `CORS_ALLOWED_ORIGINS` | Dominios permitidos (csv) | `https://tudominio.com` |
| `API_BASE_URL` | URL interna FastAPI (Opción B) | `http://127.0.0.1:8000` |
| `API_INTERNAL_KEY` | Key para endpoints internos de FastAPI | `<random-32-chars>` |
| `LOG_LEVEL` | Nivel de log | `WARNING` |
| `MAX_EXPORT_ROWS` | Límite de filas de export | `100000` |
| `SHOW_OEE_TAB` | Tab OEE activo | `false` |
| `DEBUG` | Modo debug (SIEMPRE false en prod) | `false` |
| `RATE_LIMIT_PER_MINUTE` | Límite de intentos de login | `5` |

**Paso 40 — Auditar `requirements.txt`** para cPanel

Verificar pins exactos (`==`). Para Opción A: remover `uvicorn` como dependencia de producción. Para Opción B: verificar que `uvicorn[standard]` no requiera `uvloop` (falla en algunos cPanel). Alternativa: `uvicorn` sin extras.

**Paso 41 — Crear `startup.sh`** (solo para Opción B con SSH)

Script que inicia el worker de FastAPI como background process al arrancar el Python App de cPanel.

---

## VERIFICACIÓN

1. **Audit log:** Hacer login exitoso y fallido → verificar filas en `audit_log` con `action="LOGIN_SUCCESS"` y `action="LOGIN_FAILURE"` respectivamente.
2. **Query log:** Hacer 3 requests al dashboard → verificar 3 filas en `user_query` con `start_date`, `end_date`, `line`, `interval_type` y `query_parameters` (JSON) correctos.
3. **Seguridad:** `POST /api/v1/system/cache/load/xxx` sin `X-Internal-Key` → debe responder `401`. Con key correcta → `200`.
4. **Seguridad:** `.env` sin `FLASK_SECRET_KEY` → la app debe fallar en startup con mensaje claro.
5. **CSRF:** Enviar POST al login sin token CSRF → debe responder `400 Bad Request`.
6. **Widget nuevo:** Crear `services/widgets/types/test_widget.py` con clase incorrecta → startup debe loguear error en `validate_layout_consistency()`.
7. **cPanel:** Subir proyecto, configurar variables, ejecutar `passenger_wsgi.py` → app responde en el dominio.

---

## DECISIONES

- **MetadataCache multi-tenant (descartado):** Cada cliente tiene su propia instancia de app → el singleton single-tenant es correcto para este modelo de deployment. Si en el futuro se consolida en una instancia multi-tenant, se revisita.
- **`user_query` vs modelo nuevo:** La tabla ya existe en la DB con una estructura específica. El ORM model debe mapear exactamente a esa estructura, incluyendo el typo `slq_query`.
- **`audit_log.user_id NOT NULL`:** Decidir Opción A (`user_id=0` para failures) u Opción B (migración ALTER TABLE) antes de implementar el Paso 9. Opción A no requiere cambios de DB.
- **Fire-and-forget para `QueryLogService`:** La escritura del query log no debe bloquear el response del dashboard. Si falla, se loguea el error pero el response continúa normalmente.
- **Opción A vs B cPanel:** Para shared hosting sin SSH se recomienda Opción A. Con SSH disponible, Opción B mantiene la arquitectura async-first de FastAPI.
