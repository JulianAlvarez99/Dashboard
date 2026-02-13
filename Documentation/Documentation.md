# Documentación Técnica — Camet Analytics Dashboard

Guía técnica detallada de la plataforma. Cubre la lógica de widgets, filtros, cálculos industriales, flujo de datos, seguridad y decisiones de arquitectura.

**Última actualización:** 13 Febrero 2026

---

## Tabla de Contenidos

1. [Flujo de Datos Principal](#1-flujo-de-datos-principal)
2. [Sistema de Filtros](#2-sistema-de-filtros)
3. [Agrupación de Líneas](#3-agrupación-de-líneas)
4. [Pipeline de Widgets](#4-pipeline-de-widgets)
5. [Cálculos de KPI](#5-cálculos-de-kpi)
6. [Detección de Paradas (Downtime)](#6-detección-de-paradas-downtime)
7. [Charts — Gráficos Interactivos](#7-charts--gráficos-interactivos)
8. [MetadataCache](#8-metadatacache)
9. [Base de Datos](#9-base-de-datos)
10. [Seguridad y Autenticación](#10-seguridad-y-autenticación)
11. [Frontend — Alpine.js + Chart.js](#11-frontend--alpinejs--chartjs)
12. [API REST — Endpoints](#12-api-rest--endpoints)

---

## 1. Flujo de Datos Principal

El dashboard utiliza un **pipeline de consulta única** (single-query pipeline). Una sola petición POST desde el frontend obtiene todos los datos necesarios para todos los widgets del tablero.

### Secuencia completa

```
1. Usuario hace clic en "Aplicar Filtros"
   │
2. dashboard-app.js → POST /api/v1/dashboard/data
   │  Body: { widget_ids, line_id|line_ids, dates, shift_id, interval, ... }
   │
3. FastAPI endpoint (app/api/v1/dashboard.py)
   │  ├─ Parsea DashboardDataRequest (Pydantic)
   │  └─ Construye FilterParams
   │
4. DashboardDataService.get_dashboard_data(params, widget_ids)
   │
   ├─ 4a. Determinar líneas: get_line_ids_from_params()
   │       si line_ids → usa la lista
   │       si line_id  → [line_id]
   │       si ninguno  → todas las líneas activas del cache
   │
   ├─ 4b. _fetch_all_data(line_ids, params):
   │       │
   │       ├─ fetch_detections_multi_line()
   │       │   Para cada línea:
   │       │     SELECT detection_id, detected_at, area_id, product_id
   │       │     FROM detection_line_{nombre}
   │       │     WHERE detected_at ENTRE start_dt Y end_dt
   │       │     [AND area_id IN (...)]
   │       │     [AND product_id IN (...)]
   │       │     [AND TIME(detected_at) en ventana de turno]
   │       │     ORDER BY detection_id, LIMIT 500,000
   │       │     (paginación por cursor: detection_id > cursor_id)
   │       │
   │       ├─ enrich_with_metadata()
   │       │   ┌ area_name, area_type    ← cache areas
   │       │   └ product_name, _code, _weight, _color ← cache products
   │       │
   │       ├─ enrich_with_line_metadata()
   │       │   └ line_name, line_code    ← cache production_lines
   │       │
   │       ├─ _fetch_downtime_events()
   │       │   SELECT event_id, start_time, end_time, duration, reason_code
   │       │   FROM downtime_events_{nombre}
   │       │   (paginación por cursor: event_id > cursor_id, LIMIT 10,000)
   │       │   → DataFrame con source="db"
   │       │
   │       ├─ calculate_gap_downtimes()
   │       │   Análisis de gaps entre detecciones consecutivas
   │       │   → DataFrame con source="calculated"
   │       │
   │       ├─ remove_overlapping()
   │       │   Si un gap calculado se superpone con un evento DB
   │       │   del mismo line_id → eliminar el calculado (DB gana)
   │       │
   │       └─ Merge: concat(db_downtime + calculated) → _enrich_downtime()
   │          → DashboardData(detections, downtime, params, lines_queried)
   │
   └─ 4c. Para cada widget_id:
          _process_widget(widget_id, data, is_multi_line)
          │
          ├─ Busca widget_meta en MetadataCache.widget_catalog
          ├─ Infiere widget_type via infer_widget_type(widget_name)
          ├─ Busca procesador en PROCESSOR_MAP[widget_type]
          └─ Llama: processor(widget_id, name, type, data [, aggregator])
```

### DashboardData (contenedor de datos)

Definido en `app/services/dashboard_data_service.py`:

```python
class DashboardData:
    detections: pd.DataFrame     # Detecciones enriquecidas (todas las líneas)
    downtime: pd.DataFrame       # Eventos de parada (DB + calculados, merged)
    params: FilterParams         # Filtros originales
    lines_queried: List[int]     # IDs de líneas consultadas
```

Ambos DataFrames están **enriquecidos** con metadatos del cache antes de llegar a los procesadores. Los procesadores nunca acceden a la base de datos directamente.

---

## 2. Sistema de Filtros

### Arquitectura

```
FilterFactory (factory.py)
├── BaseFilter (base.py, abstracto)
│   ├── DateRangeFilter   → type "daterange"
│   ├── DropdownFilter     → type "dropdown"
│   ├── MultiselectFilter  → type "multiselect"
│   ├── TextFilter         → type "text"
│   ├── NumberFilter       → type "number"
│   └── ToggleFilter       → type "toggle" / "checkbox"
│
FilterResolver (filter_resolver.py)
└── Fachada que resuelve configuraciones y opciones
```

### FilterConfig (dataclass)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `filter_id` | int | ID del filtro en tabla `filter` |
| `filter_name` | str | Nombre visible |
| `param_name` | str | Nombre del parámetro HTTP (`line_id`, `shift_id`, etc.) |
| `filter_type` | str | Tipo: daterange, dropdown, multiselect, text, number, toggle |
| `placeholder` | str? | Texto placeholder del input |
| `default_value` | Any? | Valor por defecto |
| `required` | bool | Si es obligatorio |
| `options_source` | str? | Fuente de opciones (ej: "production_lines", "shifts") |
| `static_options` | list? | Opciones estáticas definidas en JSON |
| `depends_on` | str? | Nombre del filtro padre para cascada |
| `ui_config` | dict? | Configuración visual adicional |

### Resolución de filtros

1. El template de dashboard renderiza con `filterConfigs` (Flask SSR)
2. `dashboard-app.js` carga opciones desde la API al iniciar:
   - `GET /api/v1/filters/options/production-lines`
   - `GET /api/v1/filters/options/shifts`
   - `GET /api/v1/filters/options/products`
3. Cuando el usuario cambia la línea (`onLineChange()`):
   - Si es un grupo/all → `isMultiLine = true`, oculta area y threshold
   - Si es línea individual → carga áreas con `GET /api/v1/filters/options/areas?line_id=X`

### Filtros en la consulta SQL

Los `FilterParams` se traducen en cláusulas WHERE en `_build_detection_query()`:

| FilterParam | Cláusula SQL |
|-------------|--------------|
| `start_date` + `start_time` | `detected_at >= :start_dt` |
| `end_date` + `end_time` | `detected_at <= :end_dt` |
| `area_ids` | `area_id IN (:area_id_0, :area_id_1, ...)` |
| `product_ids` | `product_id IN (:product_id_0, ...)` |
| `shift_id` → shift.start/end | `TIME(detected_at) >= :shift_start AND TIME(detected_at) < :shift_end` |
| turno nocturno | `TIME(detected_at) >= :shift_start OR TIME(detected_at) < :shift_end` |

---

## 3. Agrupación de Líneas

Implementado en `FilterResolver.get_production_line_options_with_groups()`.

### Estructura del dropdown de líneas

El dropdown presenta opciones en este orden:

1. **"Todas las líneas"** — auto-generado si hay >1 línea activa
   - `value: "all"`, `is_group: true`
   - `line_ids: [todos los IDs de líneas activas]`

2. **Grupos custom** — extraídos del campo `additional_filter` de la tabla `filter`
   - Formato simple: `{"alias": "Fraccionado", "line_ids": [2, 3, 4]}`
   - Formato múltiple: `{"groups": [{"alias": "...", "line_ids": [...]}, ...]}`
   - `value: "group_{filter_id}"` o `"group_{filter_id}_{idx}"`
   - `is_group: true`

3. **Líneas individuales** — cada `production_line` activa
   - `value: line_id` (int), `is_group: false`

### Comportamiento multi-línea en el frontend

Cuando `isMultiLine = true` (grupo o "todas"):
- Se envía `line_ids` (CSV) en vez de `line_id`
- Se deshabilita el filtro de `downtime_threshold`
- Se vacía el selector de áreas
- Se ocultan widgets de tipo `kpi_downtime_count` y `scatter_chart` (muestran mensaje: _"Métrica/Visualización de paradas no disponible en modo múltiples líneas"_)
- Las anotaciones de downtime en `line_chart` se suprimen
- En el desglose de OEE, se ocultan los minutos de parada cuando multi-línea

### Comportamiento multi-línea en el backend

`DashboardDataService` procesa normalmente con `line_ids` como lista. No hay diferencia lógica excepto que:
- Las detecciones se buscan iterando sobre cada `line_id`
- Los downtime events se buscan por cada línea
- Los procesadores reciben el mismo `DashboardData` con datos combinados
- El OEE calcula rendimiento **per-line** incluso con múltiples líneas (cada línea tiene su propio `production_line.performance`)

---

## 4. Pipeline de Widgets

### PROCESSOR_MAP (16 procesadores, 16 tipos)

Definido en `app/services/processors/__init__.py`:

| `widget_type` | Procesador | Categoría | Requiere `aggregator` |
|----------------|------------|-----------|----------------------|
| `kpi_total_production` | `process_kpi_production` | KPI | No |
| `kpi_total_weight` | `process_kpi_weight` | KPI | No |
| `kpi_oee` | `process_kpi_oee` | KPI | No |
| `kpi_downtime_count` | `process_kpi_downtime` | KPI | No |
| `kpi_availability` | `process_kpi_availability` | KPI | No |
| `kpi_performance` | `process_kpi_performance` | KPI | No |
| `kpi_quality` | `process_kpi_quality` | KPI | No |
| `line_chart` | `process_line_chart` | Chart | Sí |
| `bar_chart` | `process_bar_chart` | Chart | Sí |
| `pie_chart` | `process_pie_chart` | Chart | Sí |
| `comparison_bar` | `process_comparison_bar` | Chart | Sí |
| `scatter_chart` | `process_scatter_chart` | Chart | Sí |
| `downtime_table` | `process_downtime_table` | Table | No |
| `product_ranking` | `process_product_ranking` | Ranking | Sí |
| `line_status` | `process_line_status` | Ranking | Sí |
| `metrics_summary` | `process_metrics_summary` | Ranking | Sí |

### Firma de procesadores

```python
# KPI / Table:
processor(widget_id: int, name: str, wtype: str, data: DashboardData) → Dict

# Chart / Ranking (CHART_TYPES):
processor(widget_id: int, name: str, wtype: str, data: DashboardData, aggregator: DataAggregator) → Dict
```

### Inferencia del tipo de widget

`infer_widget_type(widget_name)` en `helpers.py` mapea el nombre del widget (de `widget_catalog`) al `widget_type` en `PROCESSOR_MAP`. Usa coincidencia por keywords desacentuados:

```python
# Ejemplo: "Producción Total" → strip_accents → "produccion total" → matches "produccion" → "kpi_total_production"
```

### Respuesta estándar de un widget

```json
{
  "widget_id": 1,
  "widget_name": "Producción Total",
  "widget_type": "kpi_total_production",
  "data": { "value": 1234, "unit": "unidades", "trend": null },
  "metadata": { "widget_category": "kpi" }
}
```

---

## 5. Cálculos de KPI

Todos los procesadores KPI están en `app/services/processors/kpi.py`.

### 5.1 Producción Total (`kpi_total_production`)

```
valor = count(detections WHERE area_type == "output")
```

Solo cuenta detecciones de áreas de tipo "output" (salida). Si no hay columna `area_type`, cuenta todas.

### 5.2 Peso Total (`kpi_total_weight`)

```
valor = SUM(product_weight) WHERE area_type == "output"
```

Suma el peso de cada producto detectado en áreas de salida. `product_weight` viene del enriquecimiento con la tabla `product`.

### 5.3 OEE (`kpi_oee`)

**OEE = Disponibilidad × Rendimiento × Calidad / 10000**

El resultado está en porcentaje (0-100).

#### 5.3.1 Disponibilidad (Availability)

```
Disponibilidad = ((Tiempo_Programado - Tiempo_Parada) / Tiempo_Programado) × 100
```

- **Tiempo Programado** (`scheduled_minutes`): Se calcula con `calculate_scheduled_minutes(params)`:
  - Si hay turno seleccionado: solo las horas de ese turno
  - Si no: suma de todos los turnos activos
  - Se multiplica por el número de días calendario en el rango de fechas
  - Fórmula: `daily_minutes × max(1, num_days)`

- **Duración de un turno**: Si `is_overnight=true` o `end ≤ start`, se calcula como:
  `(24h × 60 - start_minutes) + end_minutes`

- **Tiempo de Parada** (`total_downtime_minutes`): `SUM(downtime.duration) / 60`
  - Incluye tanto eventos registrados en DB como los calculados por gap analysis
  - Los eventos DB tienen prioridad (los calculados que se solapan se eliminan)

#### 5.3.2 Rendimiento (Performance)

```
Rendimiento = (Producción_Real / Producción_Teórica) × 100
```

- **Producción Real**: `count(detections WHERE area_type == "output")` (total, todas las líneas)

- **Producción Teórica**: Se calcula **POR LÍNEA** y luego se suma:
  ```
  Para cada línea L en lines_queried:
    perf_rate = production_line[L].performance   # productos/minuto (de la tabla production_line)
    line_downtime_min = SUM(downtime[line_id == L].duration) / 60
    line_operating_min = max(0, scheduled_minutes - line_downtime_min)
    total_expected += perf_rate × line_operating_min
  ```

  **IMPORTANTE**: Se usa `production_line.performance` (productos por minuto, campo de la tabla `production_line`), **NO** `product.production_std`. Cada línea tiene su propia tasa de producción esperada.

- El cap está en 100% (`min(100, valor)`)

#### 5.3.3 Calidad (Quality)

```
Calidad = (Salida / Entrada) × 100      # para líneas con ambas áreas
Calidad = 100%                            # para líneas con una sola área
```

- Se usa `get_lines_with_input_output(lines_queried)` para identificar líneas que tienen **ambas** áreas (input + output)
- Para esas líneas: `salida_q / entrada` (filtrado a detecciones solo de esas líneas)
- Líneas con solo un área (ej: solo output): `quality = 100%` por defecto
- Cap: `min(100, valor)`

#### 5.3.4 OEE Final

```python
oee = (availability / 100) × (performance / 100) × (quality / 100) × 100
```

### 5.4 Paradas (`kpi_downtime_count`)

```
count = len(downtime_df)
total_minutes = SUM(downtime.duration) / 60
```

### 5.5 KPIs Derivados

`kpi_availability`, `kpi_performance`, `kpi_quality` **delegan** a `process_kpi_oee()` para no duplicar lógica. Extraen el campo correspondiente del resultado.

---

## 6. Detección de Paradas (Downtime)

### Fuentes de paradas

| Fuente | Tabla | `source` | Prioridad |
|--------|-------|----------|-----------|
| Registrado en DB | `downtime_events_{line}` | `"db"` | Alta (operador confirmó) |
| Calculado por gap | — (en memoria) | `"calculated"` | Baja (se elimina si hay overlap con DB) |

### Gap Analysis (`downtime_calculator.py`)

El algoritmo detecta paradas analizando los **intervalos entre detecciones consecutivas**:

```
Para cada línea:
  1. Verificar que auto_detect_downtime == true
  2. Obtener threshold (override de filtro o valor DB de la línea)
  3. Ordenar detecciones por detected_at
  4. Para cada par consecutivo (t[i], t[i+1]):
     gap_sec = (t[i+1] - t[i]) en segundos
     
     Si gap_sec > threshold:  ← desigualdad ESTRICTA
       Si no hay parada abierta → abrir nueva: start = t[i]
       Actualizar end = t[i+1]
     Sino:
       Si hay parada abierta → cerrarla y emitir evento
       La producción se reanudó
  
  5. Si queda parada abierta al final → cerrarla y emitir
```

**Regla de merge**: Gaps consecutivos que superan el threshold se **fusionan** en un solo evento de parada. La producción debe reanudarse (gap ≤ threshold) para que se cierre la parada actual y pueda comenzar una nueva.

**Desigualdad estricta** (`gap_sec > threshold`): Si el gap es **exactamente** igual al threshold, se considera que la producción sigue corriendo (la siguiente detección llegó justo a tiempo).

### De-duplicación (`remove_overlapping()`)

```python
Para cada downtime calculado:
  Si existe algún downtime DB del mismo line_id
  que se superpone temporalmente → eliminar el calculado
```

Un overlap existe cuando: `calc.start < db.end AND calc.end > db.start`

### Enriquecimiento de downtime

Después de merge, se enriquece con `line_name`, `line_code` del cache, y se convierte `duration` de `timedelta` a `float` en segundos.

---

## 7. Charts — Gráficos Interactivos

### ChartRenderer (`chart-renderer.js`)

Singleton que centraliza toda la creación de gráficos Chart.js. Métodos principales:

| Método | Tipo de gráfico | Plugins activos |
|--------|-----------------|-----------------|
| `buildLineConfig()` | Line chart | zoom, annotation (downtime) |
| `buildBarConfig()` | Bar chart | zoom (si multi-dataset) |
| `buildPieConfig()` | Doughnut | — |
| `buildScatterConfig()` | Scatter | zoom |

### Zoom y Pan

Habilitado en `line_chart`, `bar_chart`, `comparison_bar`, `scatter_chart`:

| Acción | Input | Efecto |
|--------|-------|--------|
| Pan | Arrastrar | Mover la vista horizontalmente |
| Zoom wheel | Ctrl + rueda | Zoom in/out |
| Zoom drag | Ctrl + arrastrar | Selección de zona rectangular |
| Pinch | Gesture touch | Zoom en móviles |
| Reset | Doble-clic / botón | Volver al zoom original |

El toolbar de zoom se crea dinámicamente (`_createZoomToolbar()`) con texto de ayuda y botón "↺ Reset Zoom" que aparece solo después de hacer zoom/pan.

### Anotaciones de Downtime

En los `line_chart`, cada evento de downtime se muestra como un **box semitransparente**:
- **Rojo** (`rgba(239,68,68,0.15)`): Paradas detectadas por gap
- **Naranja** (`rgba(249,115,22,0.15)`): Paradas con incidente registrado
- Label: `⏸ {duration}min`

En **modo multi-línea** (`isMultiLine=true`), las anotaciones se suprimen (demasiados datos de líneas mixtas confundirían la visualización).

### Curvas de línea

4 modos configurables desde el filtro `curve_type`:

| Modo | `tension` | `stepped` | `fill` |
|------|-----------|-----------|--------|
| `smooth` (default) | 0.4 | false | false |
| `linear` | 0 | false | false |
| `stepped` | 0 | true | false |
| `stacked` | 0.4 | false | `"origin"` |

### Scatter Chart (Mapa de Paradas)

Eje X: Hora del día (0-24), Eje Y: Duración en minutos. Cada punto es un evento de parada. **Solo disponible en modo línea individual** (single line).

Tooltip personalizado muestra: `hora:minuto — duración min | razón`

---

## 8. MetadataCache

Singleton definido en `app/core/cache.py`. Se carga una vez al **startup** de FastAPI y se mantiene en memoria.

### Tablas cacheadas

| Clave | Tabla origen | DB | Indexado por |
|-------|-------------|-----|-------------|
| `production_lines` | `production_line` | tenant | `line_id` |
| `areas` | `area` | tenant | `area_id` |
| `products` | `product` | tenant | `product_id` |
| `shifts` | `shift` (activos) | tenant | `shift_id` |
| `filters` | `filter` (activos) | tenant | `filter_id` |
| `failures` | `failure` | tenant | `failure_id` |
| `incidents` | `incident` | tenant | `incident_id` |
| `widget_catalog` | `widget_catalog` | global | `widget_id` |

### Comportamiento

- **Thread-safety**: Protegido con `asyncio.Lock` durante `load_all()`
- **Singleton**: Patrón `__new__` que retorna la misma instancia
- **Refresh**: `await metadata_cache.refresh()` recarga todo
- **No auto-expira**: No hay TTL automático; se recarga manualmente o al reiniciar
- **Columnas cargadas**: Todas las columnas de cada tabla (incluido `performance` de `production_line`)

### Uso en procesadores

Los procesadores NUNCA hacen queries a la DB. Todo se resuelve contra el cache:

```python
# Ejemplo en kpi.py
line_meta = metadata_cache.get_production_line(lid)
perf_rate = line_meta.get("performance", 0)
```

---

## 9. Base de Datos

### Modelo Multi-Tenant

```
camet_global (base global)
├── tenant          → empresas registradas
├── user            → usuarios con tenant_id FK
├── widget_catalog  → catálogo global de widgets
├── dashboard_template → templates de dashboards
├── user_login      → auditoría de sesiones
└── audit_log       → log de acciones

db_client_{tenant} (base por tenant)
├── production_line → líneas de producción (performance, threshold, ...)
├── area            → áreas de detección (input/output, coords)
├── product         → productos (peso, color, código)
├── shift           → turnos (horarios, overnight)
├── filter          → filtros configurados (JSON additional_filter)
├── failure         → tipos de falla
├── incident        → incidentes por tipo de falla
├── detection_line_{nombre} (*)  → detecciones por línea
└── downtime_events_{nombre} (*) → paradas registradas por línea
    (*) tablas dinámicas: una por cada línea de producción
```

### Tablas Dinámicas por Línea

Las tablas de detecciones y downtime se crean por línea de producción. El nombre se construye como:

```python
table_name = f"detection_line_{line['line_name'].lower()}"
table_name = f"downtime_events_{line['line_name'].lower()}"
```

**Esquema de `detection_line_X`:**
```sql
detection_id  INT PK AUTO_INCREMENT
detected_at   DATETIME
area_id       INT FK → area
product_id    INT FK → product
```

**Esquema de `downtime_events_X`:**
```sql
event_id           INT PK AUTO_INCREMENT
last_detection_id  INT
start_time         DATETIME
end_time           DATETIME
duration           TIME / FLOAT
reason_code        VARCHAR
created_at         DATETIME
```

### DatabaseManager

- **Lazy initialization**: Los engines se crean al primer uso
- **NullPool**: Sin connection pooling, para compatibilidad con cPanel/shared hosting
- **Dual engine**: async (`aiomysql`) para FastAPI, sync (`pymysql`) para Flask
- **Dynamic tenant**: `get_tenant_engine_by_name(db_name)` crea engines dinámicos (cacheados)

**Bug conocido**: `get_tenant_engine_by_name()` referencia `settings.DB_USER` / `settings.DB_PASSWORD` que no existen como campos en Settings. Debería usar `settings.TENANT_DB_USER` / `settings.TENANT_DB_PASSWORD`.

---

## 10. Seguridad y Autenticación

### Flujo de Login

```
1. GET /auth/login → render login.html
2. POST /auth/login
   ├─ username + password del form
   ├─ authenticate_user(db_sync, username, password)
   │   ├─ SELECT user JOIN tenant WHERE username = :u
   │   ├─ Verificar tenant.is_active
   │   └─ Argon2.verify(hash, password)
   ├─ Éxito → session["user"] = { user_id, username, email, tenant_id, role, permissions, tenant_info }
   ├─ Log: INSERT INTO user_login (user_id, username, ip_address, user_agent)
   └─ Redirect → /dashboard
3. GET /auth/logout
   ├─ UPDATE user_login SET logout_at WHERE login_id
   ├─ session.clear()
   └─ Redirect → /auth/login
```

### Argon2 Password Hashing

```python
PasswordHasher(
    time_cost=2,        # iteraciones
    memory_cost=65536,  # 64 KB
    parallelism=1,      # hilos
    hash_len=32,        # largo del hash
    salt_len=16         # largo del salt
)
```

### Decorador `@login_required`

En `app/routes/auth.py`. Verifica que `session["user"]` exista. Si no, redirige a `/auth/login`.

### Roles RBAC

3 roles definidos en el campo `user.role`:
- `ADMIN` — acceso total, cross-tenant
- `MANAGER` — administración del tenant Y gestión operativa
- `OPERATOR` — operador de línea


**Nota**: Los permisos granulares por rol NO están implementados en los endpoints actuales. El decorador `@login_required` solo verifica que haya sesión, sin distinguir entre roles.

### Sesiones

- **Flask server-side sessions** con `FLASK_SECRET_KEY`
- Cookie firmada con secret key
- La sesión contiene: `user` (dict con info del usuario y tenant) + `login_id`

### API sin autenticación

**Estado actual**: La API FastAPI (puerto 8000) **NO tiene autenticación**. Los endpoints `/api/v1/*` son accesibles sin token. JWT está configurado en `Settings` (`JWT_SECRET_KEY`, `JWT_ALGORITHM`, etc.) pero no hay middleware ni dependency que lo aplique.

### CORS

Configurado en `app/main.py` con `CORSMiddleware`:
```python
allow_origins=["http://localhost:5000", "http://127.0.0.1:5000"]
allow_credentials=True
allow_methods=["*"]
allow_headers=["*"]
```

---

## 11. Frontend — Alpine.js + Chart.js

### Dashboard App (`dashboard-app.js`)

Componente Alpine.js principal que gestiona toda la interactividad del dashboard.

#### Estado reactivo

```javascript
{
  filterConfigs: [],          // Configuración de filtros (del SSR)
  widgetConfigs: [],          // Configuración de widgets (del SSR)
  loading: false,             // Spinner activo
  filterValues: {             // Valores actuales de filtros
    start_date, end_date,     // Formato YYYY-MM-DD
    start_time, end_time,     // Formato HH:MM
    line_id, shift_id,        // IDs
    product_ids, area_ids,    // Arrays
    interval, curve_type,     // Strings
    downtime_threshold,       // Int (segundos)
    show_downtime             // Boolean
  },
  options: {                  // Opciones cargadas del API
    production_line: [],      // Con groups + individuales
    shift: [], product: [], area: []
  },
  widgetResults: {},          // Datos de widgets (keyed by widget_id)
  chartInstances: {},         // Instancias Chart.js (keyed by canvas_id)
  isMultiLine: false,         // Modo multi-línea activo
  selectedLineGroup: null     // IDs de líneas del grupo seleccionado
}
```

#### Flujo de inicialización

```
1. init()
   ├─ initFilterValues()    ← fechas default: ayer a hoy, sin auto-query
   └─ loadOptions()         ← fetch parallel: lines, shifts, products
      (no se ejecuta applyFilters automáticamente)
```

#### Templates Jinja2

| Template | Ruta | Contenido |
|----------|------|-----------|
| `base.html` | `templates/base.html` | Layout base, CDN imports |
| `login.html` | `templates/auth/login.html` | Formulario de login |
| `index.html` | `templates/dashboard/index.html` | Dashboard principal |
| `header.html` | `templates/components/header.html` | Barra superior |
| `sidebar.html` | `templates/components/sidebar.html` | Panel de filtros lateral |
| `_widget_kpi.html` | `templates/dashboard/partials/` | Tarjeta KPI (con OEE breakdown) |
| `_widget_chart.html` | `templates/dashboard/partials/` | Contenedor de chart |
| `_widget_table.html` | `templates/dashboard/partials/` | Tablas de datos |

### Estilos CSS

Todo es Tailwind CSS via CDN, con archivos CSS custom para componentes específicos:
- `main.css` — reset, variables de tema oscuro
- `dashboard.css` — grid layout de 4 columnas
- `components.css` — widgets, sidebar, filtros
- `login.css` — página de login

---

## 12. API REST — Endpoints

Base URL: `http://localhost:8000/api/v1`

### Dashboard

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/dashboard/data` | Pipeline principal: obtiene todos los widgets |

**Body** (`DashboardDataRequest`):
```json
{
  "widget_ids": [1, 2, 3],
  "line_id": 1,
  "line_ids": "1,2,3",
  "area_ids": "1,2",
  "product_ids": "1,2",
  "start_date": "2024-01-01",
  "end_date": "2024-01-31",
  "start_time": "06:00",
  "end_time": "22:00",
  "shift_id": 1,
  "interval": "hour",
  "curve_type": "smooth",
  "downtime_threshold": 300,
  "show_downtime": true
}
```

### Filtros

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/filters/config/{filter_id}` | Config completa de un filtro |
| GET | `/filters/configs?filter_ids=1,2,3` | Configs de múltiples filtros |
| GET | `/filters/options/production-lines` | Líneas + grupos |
| GET | `/filters/options/areas?line_id=X` | Áreas (cascade por línea) |
| GET | `/filters/options/products` | Todos los productos |
| GET | `/filters/options/shifts` | Todos los turnos |
| GET | `/filters/options/{filter_id}` | Opciones de un filtro genérico |

### Layout

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/layout/full-config` | Layout + filtros + widgets del dashboard |

### System

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/system/health` | Health check |
| GET | `/system/cache/info` | Estadísticas del cache |
| POST | `/system/cache/refresh` | Forzar recarga del cache |

### Widgets

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/widgets/catalog` | Catálogo completo de widgets |

---

_Documento técnico actualizado automáticamente. Para cambios, verificar el código fuente._
