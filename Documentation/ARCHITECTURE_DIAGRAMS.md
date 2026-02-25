# Diagramas de Arquitectura -- Camet Analytics

Diagramas técnicos actualizados del sistema.

**Última actualización:** 25 Febrero 2026
**Módulo:** `new_app/` · **Entry point:** `run_new.py`

---

## Tabla de Contenidos

1. [Flujo General del Sistema](#1-flujo-general-del-sistema)
2. [Pipeline de Datos (request completo)](#2-pipeline-de-datos-request-completo)
3. [Auto-Discovery de Widgets y Filtros](#3-auto-discovery-de-widgets-y-filtros)
4. [DataBroker -- Routing de Datos](#4-databroker----routing-de-datos)
5. [Ciclo de Vida del MetadataCache](#5-ciclo-de-vida-del-metadatacache)
6. [Sistema de Filtros (nuevo)](#6-sistema-de-filtros-nuevo)
7. [Autenticacion](#7-autenticacion)
8. [Componentes Frontend](#8-componentes-frontend)

---

## 1. Flujo General del Sistema

```
+------------------------------------------------------------------+
|                          BROWSER                                 |
|  +--------------------+   +------------------+                  |
|  |  Alpine.js State   |   |  Chart.js        |                  |
|  |  dashboard-app.js  |-->|  chart-renderer  |                  |
|  |  Filtros / Layout  |   |  Zoom / Annotate |                  |
|  +--------+-----------+   +------------------+                  |
|           |                                                      |
|  dashboard-orchestrator.js  data-engine.js  api-client.js       |
|           | POST /api/v1/dashboard/data                          |
+-----------+------------------------------------------------------+
            |
            v
+------------------------------------------+
|         FLASK  (Puerto 5000)             |
|  +------------+  +----------------------+|
|  |  auth_bp   |  |  dashboard_bp        ||
|  |  Login/Out |  |  Jinja2 SSR          ||
|  |  Sessions  |  |  @login_required     ||
|  +-----+------+  +----------------------+|
|        | authenticate_user()             |
+--------+---------------------------------+
         |
         | (Browser llama a FastAPI directamente)
         v
+------------------------------------------------------------------+
|                FASTAPI  (Puerto 8000)                            |
|                                                                  |
|  POST /api/v1/dashboard/data                                     |
|  GET  /api/v1/filters/options/*                                  |
|  GET  /api/v1/layout/full-config                                 |
|  GET  /api/v1/system/health  / POST /api/v1/system/cache/refresh |
|  POST /api/v1/broker/data                                        |
|  GET  /api/v1/detections/*                                       |
|         |                                                        |
|  +------v------------------------------------------------------+ |
|  |      DashboardOrchestrator  (pipeline.py)                   | |
|  |                                                             | |
|  |  1. FilterEngine.validate_input(user_params)                | |
|  |  2. LineResolver.resolve(cleaned)  --> [line_ids]           | |
|  |  3. WidgetResolver.resolve(tenant, role) --> class_names    | |
|  |  4. DetectionService.fetch(session, line_ids, cleaned)      | |
|  |  5. DowntimeService.fetch(session, line_ids, cleaned)       | |
|  |     +- DB downtime + gap analysis --> dedup --> merge        | |
|  |  6. DataBroker.resolve(widget_names, master_df)             | |
|  |     +- internal --> slice DataFrame by required_columns     | |
|  |     +- external --> ExternalAPIService (async concurrent)   | |
|  |  7. WidgetEngine.process_widgets(names, payloads)           | |
|  |     +- auto-discovery --> Class(ctx).process() --> Result   | |
|  |  8. ResponseAssembler.assemble(ctx, results) --> JSON       | |
|  +-------------------------------------------------------------+ |
|                                                                  |
|  +-------------------------------------------------------------+ |
|  |    MetadataCache  (In-Memory Singleton)                     | |
|  |  production_lines / areas / products / shifts               | |
|  |  filters / failures / incidents / widget_catalog            | |
|  |  Cargado on-demand tras primer login del tenant             | |
|  +-------------------------------------------------------------+ |
|         |                                                        |
|  +------v------------------------------------------------------+ |
|  |   DatabaseManager  (database.py)                            | |
|  |   async: aiomysql  /  sync: pymysql  /  NullPool            | |
|  +-------------------------------------------------------------+ |
+------------------------------------------------------------------+
         |
    +----+------+
    v           v
+---------------+  +----------------------------------+
|  camet_global |  |  db_client_{tenant}              |
|  ------------ |  |  --------------------------------|
|  tenant       |  |  production_line                 |
|  user         |  |  area / product / shift          |
|  widget_cat.  |  |  filter / failure / incident     |
|  dashboard_t. |  |  detection_line_{name}  (N tabs) |
|  user_login   |  |  downtime_events_{name} (N tabs) |
|  audit_log    |  +----------------------------------+
+---------------+
```

---

## 2. Pipeline de Datos (request completo)

```
POST /api/v1/dashboard/data
{
  line_id, daterange, shift_id, area_ids,
  product_ids, interval, downtime_threshold,
  widget_ids (opcional)
}
         |
         v
+--------------------------------------------------+
|  FilterEngine.validate_input(params)             |
|  +- lee MetadataCache.filter_catalog             |
|  +- valida cada param contra su BaseFilter       |
|  +- aplica defaults si falta valor               |
|  +- retorna FilteredParams (dataclass)           |
+--------------------------------------------------+
         |
         v
+--------------------------------------------------+
|  LineResolver.resolve(cleaned_params)            |
|  +- "all" --> todos los line_ids del tenant      |
|  +- grupo custom --> line_ids del grupo          |
|  +- id individual --> [line_id]                  |
|  +- retorna [line_ids], is_multi_line            |
+--------------------------------------------------+
         |
         v
+--------------------------------------------------+
|  WidgetResolver.resolve(tenant_id, role)         |
|  +- widget_ids explicitos --> catalog lookup     |
|  +- sin widget_ids --> LayoutService             |
|    +- lee WIDGET_LAYOUT (config/widget_layout.py)|
|    +- filtra por tab + downtime_only + role      |
|  +- retorna [class_names] (e.g. "KpiOee")        |
+--------------------------------------------------+
         |         |
         v         v
+----------------+ +----------------------------------+
| DetectionSvc   | | DowntimeSvc                      |
| .fetch()       | | .fetch()                         |
|                | |                                  |
| SELECT * FROM  | | SELECT * FROM                    |
| detection_line | | downtime_events_{name}           |
| _{name}        | | + gap_analysis()                 |
| WHERE date,    | | + remove_overlapping()           |
|   line, shifts | | + merge con detections           |
+-------+--------+ +----------------------------------+
        |                  |
        +--------+---------+
                 |
                 v
+--------------------------------------------------+
|  master_df = detections (enriquecido con         |
|             product, area, shift info)           |
|  downtime_df = downtime (limpio, dedup)          |
+--------------------------------------------------+
                 |
                 v
+--------------------------------------------------+
|  DataBroker.resolve(widget_names, master_df)     |
|           |                |                     |
|    internal?          external?                  |
|           |                |                     |
|    slice DF by       ExternalAPIService          |
|    required_columns  asyncio.gather([...])       |
|           |                |                     |
|    WidgetPayload     WidgetPayload               |
|    (df=slice,        (json=response,             |
|     source=internal)  source=external)           |
+--------------------------------------------------+
                 |
                 v
+--------------------------------------------------+
|  WidgetEngine.process_widgets()                  |
|  para cada widget_name:                          |
|    +- _camel_to_snake(class_name)                |
|    +- importlib.import_module(module_path)       |
|    +- Class(ctx=WidgetContext).process()         |
|    +- --> WidgetResult(data, chart_type, ...)    |
+--------------------------------------------------+
                 |
                 v
+--------------------------------------------------+
|  ResponseAssembler.assemble(ctx, results)        |
|  {                                               |
|    "widgets": { name: WidgetResult... },         |
|    "metadata": { lines, daterange, ... },        |
|    "raw_data": [...],  (si include_raw=True)     |
|    "raw_downtime": [...]                         |
|  }                                               |
+--------------------------------------------------+
```

---

## 3. Auto-Discovery de Widgets y Filtros

### Widgets (WidgetEngine)

```
class_name = "KpiOee"
       |
       v
_camel_to_snake("KpiOee") --> "kpi_oee"
       |
       v
importlib.import_module(
  "new_app.services.widgets.types.kpi_oee"
)
       |
       v
getattr(module, "KpiOee")  --> clase KpiOee
       |
       v
KpiOee(ctx=WidgetContext(df, downtime_df, params))
       |
       v
.process()  --> WidgetResult(
                  data={value, delta, trend...},
                  chart_type="kpi",
                  chart_height=120,
                  title="OEE",
                  ...
                )
```

### Filtros (FilterEngine)

```
filter_id = "production_line"
       |
       v
Construye class_name: "ProductionLineFilter"
       |
       v
_camel_to_snake("ProductionLineFilter") --> "production_line_filter"
       |
       v
importlib.import_module(
  "new_app.services.filters.types.production_line_filter"
)
       |
       v
getattr(module, "ProductionLineFilter")  --> clase
       |
       v
.get_options(parent_values) --> [FilterOption(
                                   value="1",
                                   label="Linea A",
                                   group=None
                                 ), ...]
```

### Nombres de archivos (convencion)

```
Clase           --> Archivo
KpiOee          --> kpi_oee.py
KpiAvailability --> kpi_availability.py
ProductionTimeChart --> production_time_chart.py
ProductionLineFilter --> production_line_filter.py
DateRangeFilter --> date_range_filter.py

Regla: CamelCase --> snake_case + .py
       Importado desde types/ en el paquete correspondiente
```

---

## 4. DataBroker -- Routing de Datos

```
WidgetCatalog DB
{
  widget_name:      "kpi_oee",
  data_source:      "internal",     <-- o "external"
  external_api_key: null            <-- o "my_api_key"
}
       |
       v
DataBroker.resolve(widget_names, master_df)
       |
       +--- "internal" ----> slice master_df por required_columns
       |                              |
       |                        WidgetPayload(
       |                          df=sliced_df,
       |                          source="internal"
       |                        )
       |
       +--- "external" ---> ExternalAPIService.fetch(api_key)
                                     |
                              Lee external_apis.yml:
                              {
                                my_api_key:
                                  url: "https://api.example.com/data"
                                  method: GET
                                  auth: bearer_token
                                  timeout: 10
                              }
                                     |
                              asyncio.gather (concurrent)
                                     |
                              WidgetPayload(
                                json=response_data,
                                source="external"
                              )
```

### Widget Layout Config

```python
# config/widget_layout.py
WIDGET_LAYOUT = {
    "KpiOee": {
        "tab":           "overview",
        "col_span":      1,
        "row_span":      1,
        "order":         1,
        "downtime_only": False,
    },
    "DowntimeTable": {
        "tab":           "downtime",
        "col_span":      4,
        "row_span":      2,
        "order":         1,
        "downtime_only": True,   # Solo si hay datos de downtime
    },
    ...
}
GRID_COLUMNS = 4
```

---

## 5. Ciclo de Vida del MetadataCache

```
       FastAPI startup
           |
           | (NO se carga aqui -- lazy loading)
           v
    MetadataCache._instances = {}

           |
   POST /auth/login (Flask)
           |
           v
    authenticate_user() --> session["user"] = {tenant_id: X}

           |
   Primera peticion a FastAPI con tenant_id=X
           |
           v
    MetadataCache.get_instance(tenant_id=X)
           |
       existe?
      /       \
    Si         No
    |           |
    v           v
  return     _load_from_db(tenant_id)
  cache            |
              Consultas en paralelo:
              - production_lines
              - areas + products
              - shifts
              - filter_catalog
              - failure_types
              - incident_types
              - widget_catalog
                   |
              _instances[tenant_id] = cache
                   |
              return cache

   POST /api/v1/system/cache/refresh
           |
           v
   del MetadataCache._instances[tenant_id]
   --> proxima peticion recarga desde DB
```

---

## 6. Sistema de Filtros (nuevo)

```
+-------------------------------------------------------------+
|           tabla "filter" (DB tenant)                        |
|  filter_id | filter_name | filter_type | additional (JSON)  |
+------------------------------+------------------------------+
                               |
                  MetadataCache.filter_catalog
                               |
                               v
+-------------------------------------------------------------+
|  FilterEngine                                               |
|                                                             |
|  get_all(filter_ids?, parent_values?)                       |
|  +- auto-discovery por filter_id                            |
|  +- ProductionLineFilter --> get_options()                  |
|  +- DateRangeFilter      --> get_options()                  |
|  +- ShiftFilter          --> get_options()                  |
|  ...                                                        |
|                                                             |
|  validate_input(user_params)                                |
|  +- para cada param: BaseFilter.validate(value)             |
|  +- aplica defaults para params omitidos                    |
|  +- retorna FilteredParams                                  |
|                                                             |
|  resolve_all()                                              |
|  +- genera SQL clauses desde params validados               |
+-------------------------------------------------------------+
                               |
                               v
+-----------------------------+  +----------------------------+
|  OptionsFilter (base)       |  |  InputFilter (base)        |
|  +- DropdownFilter          |  |  +- TextFilter             |
|  +- MultiSelectFilter       |  |  +- NumberFilter           |
|  +- GroupedSelectFilter     |  |  +- DateRangeFilter        |
+-----------------------------+  |  +- ToggleFilter           |
                                 +----------------------------+

Tipos concretos (16):
  production_line_filter     shift_filter
  date_range_filter          area_filter
  product_filter             interval_filter
  downtime_threshold_filter  failure_type_filter
  incident_type_filter       line_group_filter
  comparison_filter          period_filter
  ...
```

### Estructura de BaseFilter

```python
class BaseFilter(ABC):
    filter_type: str           # "dropdown", "daterange", etc.
    param_name:  str           # key en user_params
    options_source: str        # "metadata", "static", "db"
    default_value: Any         # valor si no se envia
    required: bool             # falla si no se envia?
    depends_on: list[str]      # otros filtros padre
    ui_config: dict            # label, placeholder, etc.

    @abstractmethod
    def get_options(self, parent_values: dict) -> list[FilterOption]:
        ...

    def validate(self, value: Any) -> Any:
        ...   # normaliza + valida tipo
```

---

## 7. Autenticacion

```
            GET /auth/login
                 |
                 v
        +----------------+
        |   login.html   |
        |  (Jinja2/Flask)|
        +--------+-------+
                 | POST username + password
                 v
        +----------------------------+
        | authenticate_user()        |
        | +- SELECT user JOIN tenant |<-- camet_global (sync pymysql)
        | +- Check tenant.is_active  |
        | +- Argon2.verify(hash, pw) |
        +--------+-------------------+
                 |
          +------+------+
          |             |
          v             v
       [OK]          [FAIL]
    session["user"]  flash("Credenciales incorrectas")
    = {              redirect --> /auth/login
       user_id,
       username,
       tenant_id,
       role,
       permissions,
       tenant_info
      }
          |
          | INSERT INTO user_login (audit trail)
          v
    redirect --> /dashboard
          |
          v
    @login_required (decorador Flask)
    +- session["user"] existe? --> continuar
    +- no existe --> redirect /auth/login
```

---

## 8. Componentes Frontend

```
+----------------------------------+
|          base.html               |
|  CDN: Alpine.js, Chart.js,       |
|  Tailwind CSS, HTMX, plugins     |
+--------------+-------------------+
               | extends
+--------------v-------------------+
|         index.html               |
|  x-data="dashboardApp(...)"      |
|  +----------+  +---------------+ |
|  | header   |  |  sidebar      | |
|  | .html    |  |  filtros.html | |
|  +----------+  +---------------+ |
|  +------------------------------+ |
|  |   Grid 4 columnas            | |
|  |  +-------+  +-------+        | |
|  |  | _kpi  |  | _kpi  |  ...  | |
|  |  | .html |  | .html |        | |
|  |  +-------+  +-------+        | |
|  |  +---------------------------+ |
|  |  |   _chart.html  <canvas>   | |
|  |  +---------------------------+ |
|  |  +---------------------------+ |
|  |  |   _table.html             | |
|  |  +---------------------------+ |
|  +------------------------------+ |
+----------------------------------+
               |
+--------------v-------------------+
|       dashboard-app.js           |
|  Alpine.js component principal   |
|  +- filterValues (reactive state)|
|  +- applyFilters()  --> POST API |
|  +- onLineChange() --> cascade   |
|  +- widgetData  (response state) |
+--------------+-------------------+
               |
+--------------v-------------------+
|       api-client.js              |
|  +- fetchDashboardData(params)   |
|  +- fetchFilterOptions(id)       |
|  +- fetchLayout()                |
+--------------+-------------------+
               |
+--------------v-------------------+
|       data-engine.js             |
|  +- normalizeWidgetData()        |
|  +- buildChartDatasets()         |
|  +- applyDowntimeAnnotations()   |
+--------------+-------------------+
               |
+--------------v-------------------+
|       chart-renderer.js          |
|  ChartRenderer singleton         |
|  +- buildLineConfig()            |
|  +- buildBarConfig()             |
|  +- buildPieConfig()             |
|  +- buildScatterConfig()         |
|  +- _zoomOptions()               |
|  +- _buildDowntimeAnnotations()  |
|  +- render(canvasId, config)     |
+--------------+-------------------+
               |
+--------------v-------------------+
|   dashboard-orchestrator.js      |
|  +- coordina flujo de datos      |
|  +- gestiona ciclo de refresh    |
|  +- sincroniza estado de filtros |
+----------------------------------+
```

---

## Estructura de Archivos Clave

```
Dashboard/
  run_new.py                  Entry point (uvicorn + flask threads)
  new_app/
    main.py                   FastAPI factory + registro de routers
    flask_app.py              Flask factory
    core/
      config.py               Settings (env vars / .env)
      database.py             DatabaseManager (async + sync pools)
      auth.py                 authenticate_user(), Argon2
      cache.py                MetadataCache singleton
    api/v1/
      dashboard.py            POST /api/v1/dashboard/data
      filters.py              GET  /api/v1/filters/options/*
      layout.py               GET  /api/v1/layout/full-config
      system.py               health + cache refresh
      broker.py               POST /api/v1/broker/data
      detections.py           GET  /api/v1/detections/*
      dependencies.py         FastAPI Depends (get_session, etc.)
    services/
      orchestrator/
        pipeline.py           DashboardOrchestrator.execute()
        resolver.py           WidgetResolver
        context.py            DashboardContext (dataclass inmutable)
        assembler.py          ResponseAssembler.assemble()
      widgets/
        engine.py             WidgetEngine (auto-discovery)
        base.py               BaseWidget, WidgetContext, WidgetResult
        helpers.py            _compute_oee() (compartido por 4 KPIs)
        types/                18 widgets concretos
      filters/
        engine.py             FilterEngine (auto-discovery)
        base.py               BaseFilter, FilterConfig, FilterOption
        types/                16 filtros concretos
      broker/
        data_broker.py        DataBroker.resolve()
        external_api_service.py  llamadas HTTP async concurrentes
        api_config.py         carga external_apis.yml
        http_client.py        wrapper aiohttp
      data/
        detection_service.py  fetch detections + enriquecimiento
        downtime_service.py   fetch downtime + gap analysis
        detection_repository.py   queries DB crudas
        downtime_repository.py    queries DB crudas
        query_builder.py      WHERE clauses dinamicas
        enrichment.py         JOIN con metadata
        table_resolver.py     detection_line_{name} lookup
        line_resolver.py      resolucion de line_ids
      config/
        layout_service.py     lee WIDGET_LAYOUT, filtra por rol
    config/
      widget_layout.py        WIDGET_LAYOUT dict (tab, col_span, etc.)
      external_apis.yml       configuracion APIs externas
    routes/
      auth.py                 rutas Flask de autenticacion
      dashboard.py            rutas Flask del dashboard
    models/
      global_models.py        modelos SQLAlchemy DB global
      tenant_models.py        modelos SQLAlchemy DB tenant
    static/js/
      dashboard-app.js
      api-client.js
      data-engine.js
      chart-renderer.js
      chart-config.js
      dashboard-orchestrator.js
    templates/
      base.html
      auth/login.html
      dashboard/ (partials por tipo de widget)
```

---

_Diagramas basados en el estado real del código en `new_app/`. Última actualización: 25 Febrero 2026._
