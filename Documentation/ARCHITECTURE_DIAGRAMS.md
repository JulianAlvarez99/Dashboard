# Diagramas de Arquitectura — Camet Analytics

Diagramas técnicos actualizados del sistema.

**Última actualización:** 13 Febrero 2026

---

## 1. Flujo General del Sistema

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            BROWSER                                      │
│  ┌───────────────────┐   ┌─────────────────┐   ┌──────────────────┐   │
│  │  Alpine.js State   │   │  Chart.js        │   │  HTMX (futuro)  │   │
│  │  dashboard-app.js  │──▶│  chart-renderer  │   │                  │   │
│  │  Filtros · Layout  │   │  Zoom · Annotate │   │                  │   │
│  └────────┬──────────┘   └─────────────────┘   └──────────────────┘   │
│           │ POST /api/v1/dashboard/data                                 │
└───────────┼─────────────────────────────────────────────────────────────┘
            │
            ▼
┌───────────────────────────────────────┐
│         FLASK (Puerto 5000)           │
│  ┌─────────────┐  ┌───────────────┐ │
│  │  auth_bp     │  │ dashboard_bp  │ │
│  │  Login/Out   │  │ Render Index  │ │
│  │  Sessions    │  │ SSR + Config  │ │
│  └──────┬──────┘  └───────┬───────┘ │
│         │                  │          │
│  ┌──────▼──────────────────▼───────┐ │
│  │ Global DB (Sync pymysql)        │ │
│  │ authenticate_user()             │ │
│  └─────────────────────────────────┘ │
└───────────────────────────────────────┘
            │
            │ API calls (browser → FastAPI directamente)
            ▼
┌───────────────────────────────────────────────────────────┐
│              FASTAPI (Puerto 8000)                         │
│                                                            │
│  ┌──────────┐ ┌──────────┐ ┌────────┐ ┌───────────────┐ │
│  │ dashboard │ │ filters  │ │ layout │ │ system/widgets│ │
│  │  .py      │ │  .py     │ │  .py   │ │     .py       │ │
│  └─────┬────┘ └────┬─────┘ └───┬────┘ └──────┬────────┘ │
│        │           │           │              │           │
│  ┌─────▼───────────▼───────────▼──────────────▼────────┐ │
│  │                  SERVICE LAYER                       │ │
│  │  DashboardDataService                                │ │
│  │  ├─ FilterResolver                                   │ │
│  │  ├─ DataAggregator (fetch + enrich)                  │ │
│  │  ├─ DowntimeCalculator (gap analysis)                │ │
│  │  └─ PROCESSOR_MAP (16 tipos de widget)               │ │
│  │     ├─ kpi.py (7 KPIs)                              │ │
│  │     ├─ charts/ (5 tipos de gráfico)                  │ │
│  │     ├─ tables.py (downtime_table)                    │ │
│  │     └─ ranking/ (3 tipos)                            │ │
│  └───────────────────────┬─────────────────────────────┘ │
│                          │                                │
│  ┌───────────────────────▼─────────────────────────────┐ │
│  │            MetadataCache (In-Memory)                 │ │
│  │  production_lines │ areas │ products │ shifts        │ │
│  │  filters │ failures │ incidents │ widget_catalog     │ │
│  └───────────────────────┬─────────────────────────────┘ │
│                          │                                │
│  ┌───────────────────────▼─────────────────────────────┐ │
│  │         DatabaseManager (Async aiomysql)             │ │
│  │         NullPool · Cursor pagination                 │ │
│  └───────────────────────┬─────────────────────────────┘ │
└──────────────────────────┼────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           ▼                               ▼
┌───────────────────┐           ┌───────────────────────┐
│   camet_global    │           │  db_client_{tenant}   │
│   ───────────     │           │  ──────────────────   │
│   tenant          │           │  production_line      │
│   user            │           │  area                 │
│   widget_catalog  │           │  product / shift      │
│   dashboard_templ │           │  filter / failure     │
│   user_login      │           │  incident             │
│   audit_log       │           │  detection_line_X (N) │
└───────────────────┘           │  downtime_events_X(N) │
                                └───────────────────────┘
```

---

## 2. Pipeline de Datos (Single Query)

```
                    POST /api/v1/dashboard/data
                    { widget_ids, line_id, dates, ... }
                              │
                              ▼
                    ┌─────────────────────┐
                    │ FilterParams.from_  │
                    │ dict(request)       │
                    └─────────┬───────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │ get_line_ids_from_  │
                    │ params()            │
                    │ line_ids o [line_id]│
                    │ o todas las activas │
                    └─────────┬───────────┘
                              │
                    ┌─────────▼───────────┐
                    │  _fetch_all_data()  │
                    │                     │
                    │  ┌─────────────┐    │
                    │  │ detections  │    │
                    │  │ per line    │◄───│── detection_line_{name}
                    │  │ + enrich    │    │
                    │  └──────┬──────┘    │
                    │         │            │
                    │  ┌──────▼──────┐    │
                    │  │ DB downtime │◄───│── downtime_events_{name}
                    │  │ source="db" │    │
                    │  └──────┬──────┘    │
                    │         │            │
                    │  ┌──────▼──────┐    │
                    │  │ Gap calc    │    │
                    │  │ source=     │    │
                    │  │ "calculated"│    │
                    │  └──────┬──────┘    │
                    │         │            │
                    │  ┌──────▼──────┐    │
                    │  │ remove_     │    │
                    │  │ overlapping │    │
                    │  │ (DB wins)   │    │
                    │  └──────┬──────┘    │
                    │         │            │
                    │  ┌──────▼──────┐    │
                    │  │ MERGE       │    │
                    │  │ + enrich    │    │
                    │  └──────┬──────┘    │
                    └─────────┼───────────┘
                              │
                    ┌─────────▼───────────┐
                    │   DashboardData     │
                    │   .detections (DF)  │
                    │   .downtime (DF)    │
                    │   .params           │
                    │   .lines_queried    │
                    └─────────┬───────────┘
                              │
                    ┌─────────▼───────────┐
                    │  for widget_id:     │
                    │  ┌─────────────────┐│
                    │  │ infer_widget_   ││
                    │  │ type(name)      ││
                    │  └────────┬────────┘│
                    │           │          │
                    │  ┌────────▼────────┐│
                    │  │ PROCESSOR_MAP   ││
                    │  │ [widget_type]   ││
                    │  └────────┬────────┘│
                    │           │          │
                    │  ┌────────▼────────┐│
                    │  │ processor(...)  ││
                    │  │ → widget dict   ││
                    │  └─────────────────┘│
                    └─────────┬───────────┘
                              │
                              ▼
                    { widgets: {...}, metadata: {...} }
```

---

## 3. Sistema de Filtros

```
┌──────────────────────────────────────────────────────┐
│                  tabla "filter" (DB)                   │
│  filter_id │ filter_name │ additional_filter (JSON)   │
└──────────────────────┬───────────────────────────────┘
                       │ MetadataCache.get_filters()
                       ▼
┌──────────────────────────────────────────────────────┐
│                 FilterResolver                        │
│                                                       │
│  resolve_filter(filter_id)                            │
│  ├─ _parse_filter_config(data) → FilterConfig         │
│  ├─ FilterFactory.create(config) → BaseFilter subclass│
│  └─ filter.get_options(parent_values) → [FilterOption]│
│                                                       │
│  get_production_line_options_with_groups()             │
│  ├─ 1. "Todas las líneas" (si >1)                    │
│  ├─ 2. Grupos custom (from additional_filter JSON)    │
│  │   ├─ {"alias": "X", "line_ids": [2,3]}            │
│  │   └─ {"groups": [{alias, line_ids}, ...]}          │
│  └─ 3. Líneas individuales                            │
└──────────────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│                 FilterFactory                         │
│  "daterange"  → DateRangeFilter                       │
│  "dropdown"   → DropdownFilter                        │
│  "multiselect"→ MultiselectFilter                     │
│  "text"       → TextFilter                            │
│  "number"     → NumberFilter                          │
│  "toggle"     → ToggleFilter                          │
│  "checkbox"   → ToggleFilter (alias)                  │
└──────────────────────────────────────────────────────┘
```

---

## 4. Flujo de Autenticación

```
            GET /auth/login
                 │
                 ▼
        ┌────────────────┐
        │   login.html   │
        │  (Flask Jinja2) │
        └────────┬───────┘
                 │ POST username + password
                 ▼
        ┌────────────────────────────┐
        │ authenticate_user()        │
        │ ├─ SELECT user JOIN tenant │◄── camet_global (sync)
        │ ├─ Check tenant.is_active  │
        │ └─ Argon2.verify(hash, pw) │
        └────────┬───────────────────┘
                 │
          ┌──────┼──────┐
          │ OK   │      │ Fail
          ▼      │      ▼
   session["user"] =    flash("error")
   { user_id,           redirect(login)
     username,
     tenant_id,
     role,
     permissions,
     tenant_info }
          │
          │ INSERT INTO user_login
          │ (audit trail)
          ▼
   redirect → /dashboard
          │
          ▼
   @login_required
   ├─ session["user"] existe? → continuar
   └─ no → redirect /auth/login
```

---

## 5. Cálculo OEE

```
                    ┌─────────────────────────────────────┐
                    │           DATOS DE ENTRADA           │
                    │                                      │
                    │  detections DataFrame (enriquecido)  │
                    │  downtime DataFrame (merged)         │
                    │  params (FilterParams)               │
                    │  lines_queried [line_id, ...]        │
                    └───────────────┬─────────────────────┘
                                    │
                    ┌───────────────▼─────────────────────┐
                    │          DISPONIBILIDAD              │
                    │                                      │
                    │  scheduled = Σ(turnos) × N_días     │
                    │  downtime  = Σ(downtime.duration)/60│
                    │  A = (scheduled - downtime)          │
                    │      / scheduled × 100               │
                    └───────────────┬─────────────────────┘
                                    │
                    ┌───────────────▼─────────────────────┐
                    │          RENDIMIENTO                  │
                    │                                      │
                    │  real_output = count(area_type==out) │
                    │                                      │
                    │  Para cada línea L:                  │
                    │    rate = line[L].performance        │
                    │    dt_L = Σ(downtime[L]) / 60       │
                    │    op_L = scheduled - dt_L           │
                    │    expected_L = rate × op_L          │
                    │                                      │
                    │  expected = Σ(expected_L)            │
                    │  P = real / expected × 100           │
                    └───────────────┬─────────────────────┘
                                    │
                    ┌───────────────▼─────────────────────┐
                    │           CALIDAD                    │
                    │                                      │
                    │  dual_lines = líneas con input+output│
                    │  Si hay dual_lines:                  │
                    │    entrada = count(dual, input)      │
                    │    salida  = count(dual, output)     │
                    │    Q = salida / entrada × 100        │
                    │  Sino:                               │
                    │    Q = 100%                          │
                    └───────────────┬─────────────────────┘
                                    │
                    ┌───────────────▼─────────────────────┐
                    │              OEE                     │
                    │                                      │
                    │  OEE = A × P × Q / 10000            │
                    │                                      │
                    │  Retorna: oee, availability,         │
                    │  performance, quality,               │
                    │  scheduled_min, downtime_min         │
                    └─────────────────────────────────────┘
```

---

## 6. Diagrama de Componentes Frontend

```
                    ┌───────────────────────────────┐
                    │         base.html             │
                    │  CDN: Alpine, Chart.js,       │
                    │  Tailwind, HTMX, plugins      │
                    └───────────┬───────────────────┘
                                │ extends
                    ┌───────────▼───────────────────┐
                    │       index.html              │
                    │  x-data="dashboardApp(...)"   │
                    │  ┌─────────┐  ┌────────────┐ │
                    │  │ header  │  │  sidebar   │ │
                    │  │  .html  │  │   .html    │ │
                    │  └─────────┘  │  Filtros   │ │
                    │               └────────────┘ │
                    │  ┌──────────────────────────┐│
                    │  │    Grid 4 columnas       ││
                    │  │  ┌──────┐ ┌──────┐      ││
                    │  │  │_kpi  │ │_kpi  │ ...  ││
                    │  │  │.html │ │.html │      ││
                    │  │  └──────┘ └──────┘      ││
                    │  │  ┌──────────────────┐   ││
                    │  │  │  _chart.html     │   ││
                    │  │  │  <canvas>        │   ││
                    │  │  └──────────────────┘   ││
                    │  │  ┌──────────────────┐   ││
                    │  │  │  _table.html     │   ││
                    │  │  └──────────────────┘   ││
                    │  └──────────────────────────┘│
                    └──────────────────────────────┘
                                │
                    ┌───────────▼───────────────────┐
                    │     dashboard-app.js          │
                    │  Alpine.js component          │
                    │  ├─ filterValues (state)      │
                    │  ├─ applyFilters() → POST     │
                    │  ├─ onLineChange() → cascade  │
                    │  └─ _renderAllCharts()         │
                    └───────────┬───────────────────┘
                                │
                    ┌───────────▼───────────────────┐
                    │     chart-renderer.js         │
                    │  ChartRenderer singleton      │
                    │  ├─ buildLineConfig()         │
                    │  ├─ buildBarConfig()          │
                    │  ├─ buildPieConfig()          │
                    │  ├─ buildScatterConfig()      │
                    │  ├─ _zoomOptions()            │
                    │  ├─ _buildDowntimeAnnotations()│
                    │  └─ render() + toolbar        │
                    └──────────────────────────────┘
```

---

_Diagramas basados en el estado actual del código. Ver [Documentation.md](Documentation.md) para detalles de implementación._
