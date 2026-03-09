# Plan de Rebuild — Camet Analytics Dashboard
**Fecha:** Marzo 2026  
**Estrategia:** Construir en capas verificables. Nada de la siguiente fase comienza hasta que la anterior esté probada y corriendo.

---

## Principios de este Rebuild

- **Cero asunciones**: cada capa se verifica antes de continuar
- **Sin login por ahora**: el dashboard arranca directo, sin sesión ni autenticación
- **Complejidad mínima en cada paso**: solo lo necesario para que funcione
- **Stack idéntico al original**: Flask + FastAPI + Alpine.js + Chart.js + Tailwind (CDN)
- **Deploy target**: cPanel con Passenger (Opción A: proceso único para evitar problemas de SSH)

---

## Vista General de las 3 Fases

```
FASE 1 — Shell             FASE 2 — Datos              FASE 3 — Lógica
─────────────────          ───────────────────          ──────────────────────
Flask + FastAPI            DB connection                Filtros (Alpine.js)
corriendo juntos     →     MetadataCache          →     Widgets con datos
Dashboard HTML             /health endpoint             Pipeline completo
sin filtros ni             Cache warmup                 Chart.js rendering
widgets reales             Metadatos bajados
```

---

## FASE 1 — Dashboard Shell (sin login, sin filtros, sin widgets)

### Objetivo
Tener Flask + FastAPI corriendo, con el dashboard HTML visible y funcional a nivel visual. Sin datos, sin filtros, sin widgets reales.

### Estructura de archivos a crear

```
proyecto/
├── run.py                          ← Entry point (arranca Flask + FastAPI juntos)
├── passenger_wsgi.py               ← cPanel entry point
├── .env.example
├── requirements.txt
│
└── dashboard_app/
    ├── __init__.py
    │
    ├── core/
    │   ├── __init__.py
    │   └── config.py               ← Settings con pydantic-settings (solo vars necesarias)
    │
    ├── flask_app.py                 ← Crea y configura la app Flask
    ├── main.py                      ← Crea la app FastAPI (con /health endpoint)
    │
    ├── routes/
    │   ├── __init__.py
    │   └── dashboard.py            ← Blueprint: GET /dashboard/ → render index.html
    │
    ├── static/
    │   ├── css/
    │   │   └── dashboard.css       ← Grid layout, tema oscuro, variables CSS
    │   └── js/
    │       └── dashboard-app.js    ← Alpine.js component (estado vacío, sin lógica)
    │
    └── templates/
        ├── base.html               ← CDN imports (Alpine, Chart.js, Tailwind)
        └── dashboard/
            └── index.html          ← Shell del dashboard: header + sidebar vacío + grid vacío
```

### Tareas detalladas

#### 1.1 — `core/config.py`
Settings mínimo con pydantic-settings:
- `FLASK_SECRET_KEY`, `DEBUG`, `ENV`
- `API_BASE_URL` (http://127.0.0.1:8000)
- `FASTAPI_PORT` (8000)
- Sin variables de DB todavía

#### 1.2 — `flask_app.py`
- Crear Flask app
- Registrar `dashboard_bp`
- Redirect de `/` → `/dashboard/`
- Manejo de errores 404/500

#### 1.3 — `main.py` (FastAPI)
- App FastAPI mínima
- Un solo endpoint: `GET /health` → `{"status": "ok"}`
- CORS configurado para Flask (localhost:5000)

#### 1.4 — `routes/dashboard.py`
- Sin `@login_required`
- Sin `_fetch_layout()` ni `_fetch_filters()`
- Solo: `render_template("dashboard/index.html")`

#### 1.5 — Templates
- `base.html`: CDN de Alpine.js 3.x, Chart.js 4.4, Tailwind CSS, chartjs-plugin-zoom
- `dashboard/index.html`: Layout de 2 columnas (sidebar + main grid), **sin widgets, sin filtros**
- Header con logo/nombre de empresa hardcodeado
- Sidebar vacío con placeholder "Filtros próximamente"
- Grid principal vacío con placeholder "Widgets próximamente"

#### 1.6 — CSS
- Copiar `dashboard.css` de `new_app` existente (tema oscuro + grid)
- Limpiar cualquier referencia a clases que no existen aún

#### 1.7 — `dashboard-app.js` (Alpine.js)
- Componente Alpine vacío: solo `init()` que hace `console.log("Dashboard ready")`
- Sin `filterValues`, sin `loadOptions()`, sin `applyFilters()`
- Preparado estructuralmente para agregar estado en Fase 3

#### 1.8 — `run.py`
- Levanta Flask en thread 1 (puerto 5000)
- Levanta uvicorn/FastAPI en thread 2 (puerto 8000)
- Para desarrollo local

#### 1.9 — `passenger_wsgi.py`
- Entry point para cPanel
- Inicia FastAPI como subprocess (igual que el actual)
- Expone `application = flask_app`

### Criterios de verificación ✅
- [ ] `python run.py` arranca sin errores
- [ ] `http://localhost:5000/dashboard/` muestra el HTML del dashboard
- [ ] `http://localhost:8000/health` retorna `{"status": "ok"}`
- [ ] No hay errores en consola del browser
- [ ] El layout visual es correcto (sidebar + grid)

---

## FASE 2 — Conexión a DB y MetadataCache

### Objetivo
Conectar a la base de datos, bajar los metadatos (líneas, productos, turnos, etc.) al cache en memoria, y exponerlos vía endpoint. El dashboard todavía no los muestra, pero están disponibles.

### Archivos nuevos/modificados

```
new_app/
├── core/
│   ├── config.py           ← Agregar variables de DB (global + tenant)
│   ├── database.py         ← Engines SQLAlchemy con NullPool (sync para cPanel)
│   └── cache.py            ← MetadataCache singleton
│
├── repositories/
│   └── metadata_repository.py  ← Queries de metadatos (líneas, productos, turnos, áreas)
│
├── services/
│   └── cache_service.py    ← Orquesta la carga del cache
│
└── routes/
    └── system.py           ← Blueprint FastAPI: GET /system/health, POST /system/cache/load
```

### Tareas detalladas

#### 2.1 — `core/config.py` (ampliar)
Agregar:
```
GLOBAL_DB_HOST, GLOBAL_DB_PORT, GLOBAL_DB_NAME
GLOBAL_DB_USER, GLOBAL_DB_PASSWORD
TENANT_DB_HOST, TENANT_DB_PORT
TENANT_DB_USER, TENANT_DB_PASSWORD
API_INTERNAL_KEY   ← para proteger endpoints internos
```

#### 2.2 — `core/database.py`
- Engine para DB global (camet_global): sync con pymysql + NullPool
- Factory para engines de tenant (db_client_{slug}): sync con pymysql + NullPool
- Razón NullPool: cPanel/Passenger recicla procesos agresivamente → "MySQL has gone away"
- `get_global_session()` y `get_tenant_session(db_name)` como context managers

#### 2.3 — `core/cache.py` (MetadataCache)
Singleton que almacena en memoria:
```python
{
  "production_lines": [...],   # id, name, description, performance
  "products":         [...],   # id, name, sku, production_std
  "shifts":           [...],   # id, name, start_time, end_time
  "areas":            [...],   # id, name, area_type
  "line_products":    {...},   # line_id → [product_ids]
  "loaded_at":        datetime,
  "tenant_id":        int,
  "db_name":          str
}
```
Métodos:
- `load_all(tenant_id, db_name)` → carga todo desde DB
- `is_loaded()` → bool
- `get_lines()`, `get_products()`, `get_shifts()`, `get_areas()` → getters tipados
- `invalidate()` → limpia el cache

#### 2.4 — `repositories/metadata_repository.py`
Queries SQL directas (sin ORM complejo):
- `get_production_lines(session)` 
- `get_products(session)`
- `get_shifts(session)`
- `get_areas(session)`
- `get_line_products(session)` → mapeo línea → productos

#### 2.5 — `services/cache_service.py`
- `load_cache(tenant_id, db_name)` → llama al repository + puebla el singleton
- Manejo de errores con logging
- Retorna `{"loaded": True, "lines": N, "products": N, ...}`

#### 2.6 — Endpoints FastAPI para el cache
```
GET  /api/v1/system/health        → estado del servidor + estado del cache
POST /api/v1/system/cache/load    → header X-Internal-Key requerido
GET  /api/v1/system/cache/status  → metadata del cache (sin datos sensibles)
```

#### 2.7 — Warmup del cache en startup (sin login)
Como no hay login, el cache se carga automáticamente al iniciar FastAPI con un `tenant_id` hardcodeado desde `.env` (variable `DEFAULT_TENANT_ID` y `DEFAULT_DB_NAME`). Esto se reemplazará con la lógica de login en el futuro.

#### 2.8 — Script de verificación
`scripts/check_cache.py`:
```
python scripts/check_cache.py
→ Conecta a DB
→ Muestra cantidad de líneas, productos, turnos, áreas
→ Confirma que el cache se puede cargar
```

### Criterios de verificación ✅
- [ ] `GET /api/v1/system/health` retorna estado del cache (loaded: true/false)
- [ ] `POST /api/v1/system/cache/load` con key correcta carga el cache
- [ ] `GET /api/v1/system/cache/status` muestra N líneas, N productos, etc.
- [ ] Sin `API_INTERNAL_KEY` → `POST /cache/load` retorna 401
- [ ] `scripts/check_cache.py` corre sin errores y muestra los metadatos
- [ ] No hay errores "MySQL has gone away" al recargar el servidor

---

# Fase 3 — Filtros y Widgets
**Objetivo:** Pipeline completo. Un filtro (`OnlyFilter`), un widget (`ProductionTimeChart`), arquitectura limpia con `.py` + `.js` separados.

---

## El Problema que Resolvemos vs. la App Anterior

En la app anterior, el JS de cada filtro y widget vivía como un **string Python** (`js_inline`). Eso generaba:
- Escape de comillas imposible de debuggear
- Sin syntax highlighting ni linting en el JS
- Strings de 200+ líneas embebidos en código Python
- Un solo archivo HTML con miles de líneas de JS inyectado

**Solución nueva:** cada filtro y widget tiene su propio archivo `.js`. El backend descubre qué archivos cargar en base a los filtros/widgets activos del tenant (misma lógica de auto-discovery que el `.py`, pero para el `.js`).

---

## Arquitectura de Archivos — Fase 3

```
dashboard_saas/
├── services/
│   ├── filters/
│   │   ├── base.py                      ← Mantener (BaseFilter, FilterConfig, etc.)
│   │   ├── engine.py                    ← Mantener + agregar _resolve_js_path()
│   │   └── types/
│   │       └── only_filter.py           ← NUEVO filtro checkbox
│   │
│   ├── widgets/
│   │   ├── base.py                      ← Mantener (BaseWidget, WidgetResult, etc.)
│   │   ├── engine.py                    ← Mantener + agregar get_js_paths()
│   │   └── types/
│   │       └── production_time_chart.py ← NUEVO widget (portado + limpio)
│   │
│   ├── data/
│   │   ├── query_builder.py             ← NUEVO: SQL dinámico usando sql_clauses
│   │   ├── detection_repository.py      ← NUEVO: fetch raw detections
│   │   └── enrichment.py                ← NUEVO: app-side JOIN con MetadataCache
│   │
│   └── orchestrator/
│       └── pipeline.py                  ← NUEVO: DashboardOrchestrator
│
├── api/
│   └── v1/
│       └── dashboard.py                 ← NUEVO endpoint POST /api/v1/dashboard/data
│
├── static/
│   └── js/
│       ├── filters/
│       │   └── only_filter.js           ← NUEVO: JS del OnlyFilter
│       ├── widgets/
│       │   └── production_time_chart.js ← NUEVO: builder Chart.js del widget
│       ├── dashboard-app.js             ← MODIFICAR: lógica de filtros + fetch
│       └── chart-renderer.js           ← NUEVO: render con WidgetChartBuilders
│
└── templates/
    └── dashboard/
        ├── index.html                   ← MODIFICAR: sidebar + grid + cargar JS
        └── partials/
            └── _widget_chart.html       ← NUEVO: partial para charts
```

---

## Contrato entre `.py` y `.js` — Regla de Naming

La regla es la misma que entre `filter_name` (DB) y el módulo `.py`:

```
OnlyFilter           →  only_filter.py      →  only_filter.js
ProductionTimeChart  →  production_time_chart.py  →  production_time_chart.js
```

**En la clase Python**, en vez de `js_inline` (string), el atributo pasa a ser:
```python
js_file = "filters/only_filter.js"       # relativo a static/js/
js_file = "widgets/production_time_chart.js"
```

**El Flask route** llama a `filter_engine.get_js_paths()` y `widget_engine.get_js_paths()` → obtiene la lista de archivos → los pasa al template → el template los carga con `<script src="{{ url_for('static', filename='js/' + f) }}">`.

---

## Parte A — OnlyFilter

### `only_filter.py`

```
Clase:        OnlyFilter
filter_type:  "checkbox"
param_name:   "only_filter"
default:      False
required:     False
js_file:      "filters/only_filter.js"
```

**`validate(value)`:**
- Acepta: `True`, `False`, `"true"`, `"false"`, `1`, `0`, `None`
- Retorna `True` siempre (es un checkbox, no puede tener valor inválido)

**`to_sql_clause(value)`:**
```python
def to_sql_clause(self, value):
    if not value:
        return None  # checkbox desmarcado → no agrega cláusula
    
    # La hora y fecha específicas vienen de additional_filter en la DB row
    # Ejemplo DB row: {"target_date": "2025-01-15", "target_hour": 14}
    target_date = self.config.ui_config.get("target_date")
    target_hour = self.config.ui_config.get("target_hour", 0)
    
    if not target_date:
        return None
    
    # Retorna cláusula SQL para un rango de 1 hora
    start = f"{target_date} {target_hour:02d}:00:00"
    end   = f"{target_date} {target_hour:02d}:23:59"
    
    clause = "detected_at BETWEEN :only_start AND :only_end"
    params = {"only_start": start, "only_end": end}
    return clause, params
```

**`to_dict()`** — serialización para el template Jinja2:
```python
{
    "filter_id": 1,
    "class_name": "OnlyFilter",
    "filter_type": "checkbox",
    "param_name": "only_filter",
    "label": "Solo hora específica",
    "default_value": False,
    "js_file": "filters/only_filter.js"
}
```

### `only_filter.js`

Este archivo contiene los **event handlers de Alpine.js** para el filtro:

```javascript
// Registrado en window.FilterHandlers (namespace limpio, sin colisiones)
window.FilterHandlers = window.FilterHandlers || {};
window.FilterHandlers['OnlyFilter'] = {
    
    // Llamado cuando el checkbox cambia
    onChange(filterValues, newValue) {
        filterValues['only_filter'] = Boolean(newValue);
    },
    
    // Serialización: qué se envía al POST
    serialize(filterValues) {
        return { only_filter: Boolean(filterValues['only_filter']) };
    },
    
    // Validación client-side (antes del POST)
    validate(filterValues) {
        return { valid: true, error: null };
    }
};
```

---

## Parte B — ProductionTimeChart

### `production_time_chart.py`

```
Clase:        ProductionTimeChart
render:       "chart"
chart_type:   "line_chart"
chart_height: "600px"
tab:          "produccion"
col_span:     4
row_span:     2
order:        1
js_file:      "widgets/production_time_chart.js"
```

**`required_columns`:**
```python
["detected_at", "area_type", "line_id", "product_name", "product_color"]
```

**`process(self) -> WidgetResult`** — lógica completa:

```
1. Si df vacío → retornar WidgetResult vacío con metadata.empty = True

2. Resamplear por intervalo (hour/day/etc.) y product_name:
   df.groupby([pd.Grouper(key="detected_at", freq=freq), "product_name"])
   → contar filas (= unidades producidas)

3. Construir time index completo (sin gaps, fill_value=0)

4. Por cada product_name → un dataset:
   {
     "label": product_name,
     "data": [valores por intervalo],
     "borderColor": product_color,
     "backgroundColor": product_color + "14"  (8% opacity)
   }

5. Calcular class_details: por label de tiempo → {clase: count}
   → para tooltips enriquecidos en el frontend

6. Obtener downtime_events del contexto (si existe)

7. Retornar:
   {
     "labels": [...],
     "datasets": [...],
     "class_details": {...},
     "downtime_events": [...],
     "curve_type": params.get("curve_type", "smooth"),
     "show_downtime": params.get("show_downtime", True),
     "interval": params.get("interval", "hour")
   }
```

**Helpers en el mismo archivo** (sin importar de otro módulo si son simples):
- `_get_freq(interval)` → `"H"` / `"D"` / `"15min"`
- `_format_labels(index, interval)` → lista de strings formateados
- `_alpha(hex_color, opacity)` → `"rgba(r,g,b,opacity)"`

### `production_time_chart.js`

```javascript
// Registrado en WidgetChartBuilders (namespace Chart.js)
window.WidgetChartBuilders = window.WidgetChartBuilders || {};
window.WidgetChartBuilders['ProductionTimeChart'] = {
    
    zoomable: true,
    toggleable: true,   // permite toggle línea/barras
    
    // Punto de entrada principal
    buildConfig(data, options) {
        // options = { isMultiLine, mode ('line'|'bar'), resetBtn }
        // data    = lo que retorna process() en el backend
        
        const asBar = (options.mode || 'line') === 'bar';
        const stacked = data.curve_type === 'stacked';
        
        const datasets = this._buildDatasets(data, asBar, stacked);
        const annotations = this._buildAnnotations(data, options.isMultiLine);
        
        return {
            type: asBar ? 'bar' : 'line',
            data: { labels: data.labels || [], datasets },
            options: this._buildOptions(data, annotations, stacked, options)
        };
    },
    
    _buildDatasets(data, asBar, stacked) { ... },
    _buildAnnotations(data, isMultiLine) { ... },
    _buildOptions(data, annotations, stacked, options) { ... },
    _buildTooltips(data) { ... }
};
```

---

## Parte C — Pipeline de Datos

### Flujo completo de un request

```
POST /api/v1/dashboard/data
  Body: { widget_ids: [1], only_filter: true }
  │
  ▼
FastAPI endpoint (dashboard.py)
  │  Parsea body (Pydantic model dinámico o dict simple)
  │
  ▼
DashboardOrchestrator.run(params, widget_ids)
  │
  ├─ 1. FilterEngine.validate_input(params)
  │       → cleaned = { "only_filter": True }
  │       → errors  = {}
  │
  ├─ 2. LineResolver: obtener line_ids desde MetadataCache
  │       (sin filtro de línea por ahora → todas las activas)
  │
  ├─ 3. QueryBuilder.build(cleaned, line_ids)
  │       → SQL con WHERE + cláusulas de cada filtro activo
  │       → Para OnlyFilter(True): agrega BETWEEN :only_start AND :only_end
  │
  ├─ 4. DetectionRepository.fetch(sql, params, db_name)
  │       → DataFrame con columnas raw
  │
  ├─ 5. Enrichment.enrich(df)
  │       → App-side JOIN: agrega product_name, product_color, area_type
  │         desde MetadataCache (O(1), sin I/O adicional)
  │
  ├─ 6. WidgetEngine.process(widget_id, df, params)
  │       → Auto-discovery: "ProductionTimeChart"
  │       → ctx = WidgetContext(data=df, params=cleaned, ...)
  │       → widget.process() → WidgetResult
  │
  └─ 7. Serializar y retornar
        → { widgets: { "1": { widget_type, data, metadata } } }
```

### `query_builder.py` — Cómo aplica las cláusulas de filtro

```python
class QueryBuilder:
    def build(self, cleaned: dict, line_ids: list, table_name: str) -> tuple[str, dict]:
        sql = f"""
            SELECT detected_at, product_id, area_id, line_id
            FROM {table_name}
            WHERE 1=1
        """
        params = {}
        
        # Iterar filtros activos y pedir su cláusula SQL
        for filter_instance in filter_engine.get_all():
            pname = filter_instance.config.param_name
            value = cleaned.get(pname, filter_instance.get_default())
            
            result = filter_instance.to_sql_clause(value)
            if result:
                clause, fparams = result
                sql += f" AND {clause}"
                params.update(fparams)
        
        # Cláusula de líneas siempre presente
        if line_ids:
            placeholders = ", ".join(f":lid_{i}" for i, _ in enumerate(line_ids))
            sql += f" AND line_id IN ({placeholders})"
            params.update({f"lid_{i}": lid for i, lid in enumerate(line_ids)})
        
        return sql, params
```

---

## Parte D — Frontend Integration

### Cómo se cargan los JS en el template

**`routes/dashboard.py`** (Flask) — sin login:
```python
@dashboard_bp.route("/")
def index():
    # Obtener filtros y widgets activos del MetadataCache
    filters = filter_engine.get_all()
    widgets = widget_engine.get_all_from_cache()
    
    # Colectar JS paths (sin duplicados)
    filter_js_files = [f.js_file for f in filters if f.js_file]
    widget_js_files = [w.js_file for w in widgets if w.js_file]
    
    # Serializar config para Alpine.js
    filters_config = filter_engine.resolve_all()   # lista de dicts
    widgets_config = widget_engine.resolve_all()   # lista de dicts
    
    return render_template(
        "dashboard/index.html",
        filters_config=filters_config,
        widgets_config=widgets_config,
        filter_js_files=filter_js_files,
        widget_js_files=widget_js_files,
    )
```

**`index.html`** — carga dinámica de JS:
```html
<!-- JS de filtros activos (cargados dinámicamente por el backend) -->
{% for js_path in filter_js_files %}
<script src="{{ url_for('static', filename='js/' + js_path) }}"></script>
{% endfor %}

<!-- JS de widgets activos -->
{% for js_path in widget_js_files %}
<script src="{{ url_for('static', filename='js/' + js_path) }}"></script>
{% endfor %}
```

### Alpine.js state (`dashboard-app.js`)

```javascript
{
    filterValues: {},        // { only_filter: false, ... }
    widgetResults: {},       // { "1": { widget_type, data, metadata } }
    chartInstances: {},      // { "chart-1": ChartInstance }
    chartModes: {},          // { "1": "line" | "bar" }
    loading: false,
    hasData: false,
    
    init() {
        this._initFilterDefaults();
    },
    
    _initFilterDefaults() {
        // Leer filterConfigs del template (Jinja2)
        // Setear valores default por tipo
        (this.filterConfigs || []).forEach(fc => {
            this.filterValues[fc.param_name] = fc.default_value ?? false;
        });
    },
    
    async applyFilters() {
        this.loading = true;
        try {
            const body = this._serializeFilters();
            const res = await fetch('/api/v1/dashboard/data', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            const json = await res.json();
            this.widgetResults = json.widgets || {};
            this.hasData = true;
            this._renderCharts();
        } finally {
            this.loading = false;
        }
    },
    
    _serializeFilters() {
        // Usar FilterHandlers si existe para el filtro, o raw value
        const out = { widget_ids: this.widgetConfigs.map(w => w.widget_id) };
        (this.filterConfigs || []).forEach(fc => {
            const handler = window.FilterHandlers?.[fc.class_name];
            if (handler?.serialize) {
                Object.assign(out, handler.serialize(this.filterValues));
            } else {
                out[fc.param_name] = this.filterValues[fc.param_name];
            }
        });
        return out;
    },
    
    _renderCharts() {
        Object.values(this.widgetResults).forEach(wd => {
            if (wd.widget_type === 'chart') {
                ChartRenderer.render(
                    wd.widget_name,
                    wd,
                    this.chartInstances,
                    false,
                    0,
                    this.chartModes[wd.widget_id] || 'line'
                );
            }
        });
    },
    
    toggleWidgetMode(widgetId, mode) {
        this.chartModes[widgetId] = mode;
        const wd = this.widgetResults[widgetId];
        if (wd) ChartRenderer.render(wd.widget_name, wd, this.chartInstances, false, 0, mode);
    }
}
```

---

## Orden de Construcción

### Semana 1 — Infraestructura y Filtro
1. `services/filters/base.py` → agregar `js_file` como atributo de clase (reemplaza `js_inline`)
2. `services/filters/engine.py` → agregar `get_js_paths()`, remover lógica de `js_inline`
3. `services/filters/types/only_filter.py` → implementación completa
4. `static/js/filters/only_filter.js` → handlers Alpine.js
5. `templates/dashboard/index.html` → sidebar con filtro checkbox + carga dinámica de JS
6. **Test:** `/dashboard/` muestra el checkbox, JS cargado, sin errores de consola

### Semana 2 — Pipeline de Datos
7. `services/data/query_builder.py` → SQL dinámico con `to_sql_clause()`
8. `services/data/detection_repository.py` → fetch raw detections
9. `services/data/enrichment.py` → app-side JOIN con MetadataCache
10. `api/v1/dashboard.py` → endpoint POST básico (sin orchestrator completo)
11. **Test:** POST con `{only_filter: true}` → retorna datos filtrados

### Semana 3 — Widget
12. `services/widgets/base.py` → reemplazar `js_inline` por `js_file`
13. `services/widgets/engine.py` → agregar `get_js_paths()`
14. `services/widgets/types/production_time_chart.py` → implementación completa con helpers
15. `static/js/widgets/production_time_chart.js` → builder Chart.js completo
16. `static/js/chart-renderer.js` → render con `WidgetChartBuilders[widgetName]`
17. `templates/dashboard/partials/_widget_chart.html` → partial HTML del chart
18. **Test:** Dashboard completo con datos reales y gráfico funcionando

---

## Criterios de Verificación (por paso)

### Al terminar la infraestructura de filtros
- [ ] `filter_engine.get_all()` retorna `[OnlyFilter]`
- [ ] `filter_engine.get_js_paths()` retorna `["filters/only_filter.js"]`
- [ ] `OnlyFilter(True).to_sql_clause()` retorna la cláusula correcta
- [ ] `OnlyFilter(False).to_sql_clause()` retorna `None`

### Al terminar el pipeline de datos
- [ ] `POST /api/v1/dashboard/data` con `{only_filter: false}` → trae todos los datos
- [ ] `POST /api/v1/dashboard/data` con `{only_filter: true}` → trae solo la hora configurada
- [ ] DataFrame enricheado tiene `product_name`, `product_color`, `area_type`

### Al terminar el widget
- [ ] `ProductionTimeChart.process()` retorna `WidgetResult` con `labels` y `datasets`
- [ ] DataFrame vacío → `metadata.empty = True`, sin crash
- [ ] `production_time_chart.js` cargado en el browser, sin errores de consola
- [ ] Toggle línea/barras funciona sin recargar la página
- [ ] Zoom/pan funciona; doble click resetea el zoom

---

## Decisiones de Diseño

| Decisión | Elección | Razón |
|----------|----------|-------|
| JS de filtros/widgets | Archivos `.js` separados | Debuggeable, cacheable por browser, sin escaping |
| Namespace JS filtros | `window.FilterHandlers['OnlyFilter']` | Evita colisiones, fácil de iterar en Alpine.js |
| Namespace JS widgets | `window.WidgetChartBuilders['ProductionTimeChart']` | Compatible con ChartRenderer existente |
| `to_sql_clause` | Retorna `(str, dict)` o `None` | Fácil de iterar en QueryBuilder sin condicionales |
| Enrich en app | Pandas + MetadataCache | Sin JOINs SQL pesados, O(1) lookup |
| Sin Pydantic dinámico | Recibir dict y validar por FilterEngine | Menos magia, más trazable |
| Fecha/hora en OnlyFilter | Viene de `additional_filter` (JSON en DB) | El filtro es configurable por tenant sin cambiar código |

## Decisiones Técnicas Confirmadas

| Decisión | Elección | Razón |
|----------|----------|-------|
| DB connection pool | NullPool | cPanel recicla procesos → "MySQL has gone away" |
| DB driver | pymysql (sync) | Compatibilidad con cPanel, sin uvloop |
| Metadatos | MetadataCache in-memory | Joins O(1) sin I/O adicional |
| Frontend reactivity | Alpine.js 3.x | Sin build step, CDN |
| Charts | Chart.js 4.4 | Maduro, bien documentado, plugins disponibles |
| CSS | Tailwind CDN | Sin build step |
| cPanel deploy | Opción A (proceso único) | Sin SSH requerido para arranque |
| Login | Se agrega después | No bloquea el desarrollo del dashboard |

---

## Stack Completo (referencia)

| Capa | Tecnología | Versión |
|------|-----------|---------|
| Backend API | FastAPI | 0.110.0 |
| Frontend SSR | Flask | 3.0.2 |
| ASGI server | Uvicorn | 0.29.0 |
| ORM/DB | SQLAlchemy (sync) | 2.0+ |
| DB driver | PyMySQL | latest |
| Validación | Pydantic v2 | 2.x |
| Procesamiento | Pandas | 2.2+ |
| Frontend state | Alpine.js | 3.x (CDN) |
| Charts | Chart.js | 4.4 (CDN) |
| CSS | Tailwind CSS | 3.x (CDN) |
| DB | MySQL | 8.0+ |

---

## Lo que NO se incluye en este rebuild (por ahora)

- ❌ Login / autenticación / sesiones
- ❌ Multi-tenant (se asume un tenant hardcodeado en `.env`)
- ❌ JWT
- ❌ Rate limiting / CSRF
- ❌ Audit log / query log
- ❌ DataBroker (APIs externas)
- ❌ Export de datos
- ❌ Tab OEE separado

Estas funcionalidades se reintroducen **después** de que el pipeline completo de Fase 3 esté funcionando.

---
