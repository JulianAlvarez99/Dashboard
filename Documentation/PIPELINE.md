# PIPELINE COMPLETO DE EJECUCIÓN
## Desde que se abre la página hasta ver los widgets con datos

---

## FASE 0 — ARRANQUE DE SERVIDORES

```
run.py
 ├── Thread 1 → uvicorn new_app.main:app  (FastAPI, puerto 8000)
 │               └── lifespan startup:
 │                     └── metadata_cache.load_all(tenant_id)   ← NO se carga aquí
 │                         (carga lazy: primera request con tenant_id)
 │
 └── Thread 2 → flask run                 (Flask,   puerto 5000)
                 └── registra blueprints:
                       auth_bp   → /auth/*
                       dashboard_bp → /dashboard/*
```

---

## FASE 1 — LOGIN (una sola vez por sesión)

```
Browser: POST /auth/login  { username, password }
  │
  ▼
Flask: routes/auth.py → login()
  │
  ├── core/auth.py → authenticate_user(username, password)
  │     ├── (sync pymysql) SELECT user.*, tenant.*
  │     │   FROM user JOIN tenant
  │     │   WHERE username = ? AND tenant.is_active = 1
  │     ├── verificar tenant.is_active
  │     └── argon2.verify(stored_hash, password)  → OK / FAIL
  │
  ├── [OK] → models/global_models.py → INSERT INTO user_login (audit)
  │
  ├── core/jwt_utils.py → create_access_token(user_id, tenant_id, role)
  │     └── jwt.encode({ sub, tenant_id, role, exp }, JWT_SECRET_KEY)
  │
  ├── _build_session(user_info, login_id)
  │     └── session["user"]    = { user_id, username, tenant_id, role,
  │                                tenant_info: { db_name, company_name } }
  │         session["db_name"] = "db_client_{slug}"
  │         session["login_id"] = login_id
  │
  ├── _warmup_cache(db_name, api_internal_key, api_base_url)
  │     └── [background thread, no bloquea login]
  │           POST /api/v1/system/cache/refresh  → FastAPI carga MetadataCache
  │
  └── redirect → /dashboard/
```

---

## FASE 2 — RENDER DEL SHELL HTML (Flask)

```
Browser: GET /dashboard/
  │
  ▼
Flask: routes/dashboard.py → index()
  │  [decorador @login_required verifica session["user"]]
  │
  ├── get_current_user()  →  user = session["user"]
  ├── get_settings()      →  settings (API_BASE_URL, etc.)
  │
  ├── _fetch_layout(api_base, tenant_id, role)
  │     └── httpx.get(f"{api_base}/api/v1/layout/full-config"
  │                   ?tenant_id=X&role=ADMIN)
  │           │
  │           ▼
  │         FastAPI: api/v1/layout.py → get_full_config()
  │           ├── require_cache() → MetadataCache.get_instance(tenant_id)
  │           │     └── [si no existe] _load_from_db(tenant_id)
  │           │           ├── SELECT * FROM production_line WHERE is_active=1
  │           │           ├── SELECT * FROM area
  │           │           ├── SELECT * FROM product WHERE is_active=1
  │           │           ├── SELECT * FROM shift WHERE is_active=1
  │           │           ├── SELECT * FROM filter WHERE is_active=1
  │           │           ├── SELECT * FROM failure
  │           │           ├── SELECT * FROM incident
  │           │           └── SELECT * FROM widget_catalog (global DB)
  │           │
  │           ├── services/config/layout_service.py → get_layout_config(tenant_id, role)
  │           │     ├── SELECT widget_id FROM dashboard_template
  │           │     │   WHERE tenant_id=X AND role=Y AND is_visible=1
  │           │     └── SELECT filter_id FROM dashboard_template
  │           │         WHERE tenant_id=X AND role=Y
  │           │
  │           └── retorna: { widgets: [{widget_id, widget_name}...],
  │                          enabled_filter_ids: [1,2,3...] }
  │
  ├── _fetch_filters(api_base, enabled_filter_ids)
  │     └── httpx.get(f"{api_base}/api/v1/filters"
  │                   ?filter_ids=1,2,3)
  │           │
  │           ▼
  │         FastAPI: api/v1/filters.py → get_filters()
  │           └── filter_engine.get_all(filter_ids=[1,2,3])
  │                 ├── metadata_cache.get_filters()  → dict[filter_id, row]
  │                 ├── para cada filter_id en whitelist:
  │                 │     class_name = row["filter_name"]  # "DateRangeFilter"
  │                 │     → camel_to_snake → "date_range_filter"
  │                 │     → importlib.import_module("...filters.types.date_range_filter")
  │                 │     → getattr(module, "DateRangeFilter")()
  │                 └── retorna [BaseFilter.to_dict() por cada filtro]
  │                       { filter_id, filter_type, param_name, label,
  │                         default_value, options, depends_on }
  │
  ├── _enrich_widgets(widgets_data)
  │     └── para cada widget en widgets_data:
  │           layout = WIDGET_LAYOUT.get(widget["widget_name"])
  │             # config/widget_layout.py (dict estático en memoria)
  │           widget.update({
  │             "tab":       layout["tab"],        # "produccion" | "oee"
  │             "col_span":  layout["col_span"],   # 1-4
  │             "order":     layout["order"],
  │             "render":    widget_cls.render,    # "kpi" | "chart" | "table"
  │             "chart_type": widget_cls.chart_type,
  │             "downtime_only": layout["downtime_only"],
  │           })
  │
  └── render_template("dashboard/index.html",
          user, filters, widgets, tenant_id, role,
          api_base_url, dashboard_api_url,
          show_oee_tab, grid_columns)
        │
        └── Jinja2 renderiza:
              base.html          → CDN: Alpine.js, Chart.js, Tailwind,
              │                         chartjs-plugin-zoom,
              │                         chartjs-plugin-annotation, lucide
              └── index.html
                    ├── _filters_panel.html   (sidebar con filtros)
                    ├── _main_content.html    (grid de widgets vacíos)
                    └── <script id="dashboard-config" type="application/json">
                          {
                            filters:  [...],   ← serializado desde Flask
                            widgets:  [...],
                            lineOptions: [...],
                            widgetMeta: {...},
                            chartTypeMap: {...},
                            apiBase: "http://...:8000",
                            dashboardApiUrl: "http://...:8000/api/v1/dashboard/data",
                            tenantId: X,
                            role: "ADMIN"
                          }
                        </script>
```

**→ Browser recibe el HTML completo. La página se muestra vacía (sin datos aún).**

---

## FASE 3 — INICIALIZACIÓN JAVASCRIPT (Alpine.js)

```
Browser: parsea HTML, carga CDNs, ejecuta scripts
  │
  ▼
dashboard-app.js → dashboardApp(config)   ← x-data en <body> o <main>
  │
  ├── Parsea config desde #dashboard-config (JSON embebido)
  │
  ├── Construye initialParams
  │     └── para cada filtro en config.filters:
  │           if filter_type === 'boolean'  → initialParams[param_name] = default (false)
  │           if filter_type === 'daterange'→ initialParams[param_name] = default
  │           else                          → initialParams[param_name] = default_value | null
  │
  ├── Inicializa state Alpine:
  │     sidebarOpen: false
  │     loading: false
  │     hasData: false
  │     activeTab: 'produccion'
  │     params: { ...initialParams }      ← bound a los inputs del sidebar
  │     widgetResults: {}
  │     chartInstances: {}
  │     chartModes: {}
  │     _rawData: null
  │     _rawDowntime: null
  │     _shiftWindows: {}
  │     _lineConfig: {}
  │     _renderedTabs: new Set()
  │     _lineOptions: config.lineOptions
  │     _widgetMeta: config.widgetMeta
  │     _CHART_TYPE_MAP: config.chartTypeMap
  │
  └── init()
        └── lucide.createIcons()          ← inicializa íconos SVG
```

**→ La página está lista para interacción. El usuario configura filtros.**

---

## FASE 4 — EL USUARIO APLICA FILTROS

```
Browser: usuario selecciona línea, fechas, turno → click "Aplicar"
  │
  ▼
dashboard-app.js → applyFilters()
  └── DashboardOrchestrator.applyFilters(this)   [dashboard-orchestrator.js]
```

---

## FASE 5 — VALIDACIÓN DE FILTROS (Frontend → FastAPI)

```
DashboardOrchestrator.applyFilters(ctx)
  │
  ├── _normalizeParams(ctx.params)
  │     └── elimina null/vacíos, normaliza tipos
  │
  ├── DashboardAPI.validateFilters(apiBase, normalizedParams)
  │     └── fetch POST /api/v1/filters/validate  { ...params }
  │           │
  │           ▼
  │         FastAPI: api/v1/filters.py → validate_filters(params)
  │           └── filter_engine.validate_input(params)
  │                 ├── metadata_cache.get_filters()  → dict activo
  │                 ├── para cada BaseFilter instanciado:
  │                 │     pname = flt.config.param_name
  │                 │     raw   = params.get(pname) or flt.get_default()
  │                 │     flt.validate(raw)  → bool
  │                 └── retorna { valid: bool, errors: {}, cleaned: {} }
  │
  ├── [si !valid] → mostrar errores, abort
  │
  └── [si valid] → continuar
```

---

## FASE 6 — REQUEST AL PIPELINE PRINCIPAL

```
DashboardOrchestrator.applyFilters(ctx) [continuación]
  │
  ├── ctx.sidebarOpen = false
  │
  ├── _buildRequestBody(ctx)
  │     └── { params: normalizedParams, include_raw: true, role: "ADMIN" }
  │
  └── DashboardAPI.fetchDashboardData(dashboardApiUrl, body)
        └── fetch POST /api/v1/dashboard/data  { ...body }
```

---

## FASE 7 — FASTAPI ENDPOINT RECIBE LA REQUEST

```
FastAPI: api/v1/dashboard.py → post_dashboard_data(request, tenant_ctx)
  │
  ├── require_tenant(request)             ← Dependency
  │     ├── extrae tenant_id del body o session
  │     ├── MetadataCache.get_instance(tenant_id)  ← lazy load si no existe
  │     └── retorna TenantContext { tenant_id, db_name, role, session }
  │
  ├── build_filter_dict(request)
  │     └── convierte Pydantic model → dict plano con todos los params
  │
  └── dashboard_orchestrator.execute(
          session   = tenant_ctx.session,   ← AsyncSession (aiomysql)
          user_params = filter_dict,
          tenant_id   = tenant_ctx.tenant_id,
          role        = tenant_ctx.role,
          widget_ids  = request.widget_ids,  ← None en el caso normal
          include_raw = request.include_raw,  ← True
      )
```

---

## FASE 8 — ORCHESTRATOR: PIPELINE PRINCIPAL

```
pipeline.py → DashboardOrchestrator.execute()
  │
  ├── t0 = time.perf_counter()
  │
  │─── STEP 8.1: VALIDAR FILTROS ─────────────────────────────────
  │
  ├── _validate_filters(user_params)
  │     └── filter_engine.validate_input(user_params)
  │           ├── metadata_cache.get_filters()
  │           ├── para cada filtro activo:
  │           │     instancia via auto-discovery (importlib, caché de clases)
  │           │     raw = user_params.get(param_name) or default
  │           │     validate(raw) → bool
  │           │     cleaned[param_name] = raw
  │           └── retorna cleaned dict (best-effort, no falla por errores)
  │
  │─── STEP 8.2: RESOLVER LÍNEAS ─────────────────────────────────
  │
  ├── line_resolver.resolve(cleaned)
  │     ├── cleaned.get("line_id") → "all" | "group_X" | int | None
  │     ├── si "all"   → metadata_cache.get_production_lines().keys()
  │     ├── si "group_X" → lookup grupo personalizado → [line_ids]
  │     ├── si int     → [line_id]
  │     └── retorna [line_ids]   e.g. [1, 2]
  │
  │─── STEP 8.3: RESOLVER WIDGETS ────────────────────────────────
  │
  ├── WidgetResolver.resolve(tenant_id, role, widget_ids=None)
  │     ├── [si widget_ids explícitos] → lookup en widget_catalog → class_names
  │     └── [caso normal] layout_service.get_layout_config(tenant_id, role)
  │               ├── SELECT widget_id FROM dashboard_template
  │               │   WHERE tenant_id=X AND role=Y AND is_visible=1
  │               ├── metadata_cache.get_widget_catalog()
  │               │   → dict[widget_id, {widget_name, ...}]
  │               ├── WIDGET_LAYOUT[widget_name] → { tab, col_span, downtime_only }
  │               └── retorna ([class_names], widget_catalog)
  │                     e.g. ["KpiTotalProduction", "ProductionTimeChart",
  │                            "DowntimeTable", "KpiOee", ...]
  │
  │─── STEP 8.4: CONSTRUIR CONTEXTO DE DATOS ─────────────────────
  │
  └── _build_context(session, cleaned, line_ids, widget_names, widget_catalog)
```

---

## FASE 9 — FETCH DE DETECCIONES

```
_build_context() → detection_service.get_enriched_detections(
                       session, line_ids=[1,2], cleaned)
  │
  ├── partition_manager.get_partition_hint(cleaned["daterange"])
  │     └── calcula "PARTITION (p202601, p202602)" desde las fechas
  │         (optimización MySQL RANGE partition)
  │
  ├── detection_repository.fetch_detections_multi_line(
  │       session, line_ids, cleaned, partition_hint)
  │     │
  │     └── para cada line_id en [1, 2]:
  │           table_name = table_resolver.detection_table(line_id)
  │             └── metadata_cache.get_production_lines()[line_id]["line_slug"]
  │                 → "detection_line_tecmar1"
  │           │
  │           fetch_detections(session, table_name, cleaned, partition_hint)
  │             │
  │             └── LOOP cursor-paginated (hasta MAX_TOTAL_ROWS=100k):
  │                   sql, params = query_builder.build_detection_query(
  │                       table_name = "detection_line_tecmar1",
  │                       cleaned    = cleaned,
  │                       cursor_id  = 0,
  │                       limit      = 10_000,
  │                       partition_hint = "PARTITION (p202601)"
  │                   )
  │                   # SQL generado:
  │                   # SELECT detection_id, detected_at, area_id, product_id
  │                   # FROM detection_line_tecmar1 PARTITION (p202601)
  │                   # WHERE detection_id > 0
  │                   #   AND detected_at BETWEEN :date_from AND :date_to
  │                   #   AND TIME(detected_at) BETWEEN :shift_start AND :shift_end
  │                   #   AND area_id IN (:area_1, :area_2)
  │                   #   AND product_id IN (:prod_1)
  │                   # ORDER BY detection_id LIMIT 10000
  │                   │
  │                   result = await session.execute(text(sql), params)
  │                   rows   = result.mappings().all()
  │                   batch_df = pd.DataFrame([dict(r) for r in rows])
  │                   cursor_id = batch_df["detection_id"].max()
  │                   [repite hasta len(rows) < limit]
  │           │
  │           df["line_id"] = line_id
  │           dataframes.append(df)
  │
  └── df = pd.concat(dataframes, ignore_index=True)
        → raw DataFrame:
          columns: [detection_id, detected_at, area_id, product_id, line_id]
          shape:   (N_rows, 5)
  │
  └── enrichment.enrich_detections(df)
        ├── _apply_area_columns(df)
        │     areas = metadata_cache.get_areas()
        │     df["area_name"] = df["area_id"].map({area_id: area_name, ...})
        │     df["area_type"] = df["area_id"].map({area_id: area_type, ...})
        │
        ├── _apply_product_columns(df)
        │     products = metadata_cache.get_products()
        │     df["product_name"]   = df["product_id"].map(...)
        │     df["product_code"]   = df["product_id"].map(...)
        │     df["product_color"]  = df["product_id"].map(...)
        │     df["product_weight"] = df["product_id"].map(...)
        │
        ├── _apply_line_columns(df)
        │     lines = metadata_cache.get_production_lines()
        │     df["line_name"] = df["line_id"].map(...)
        │     df["line_code"] = df["line_id"].map(...)
        │
        └── _ensure_datetime(df)
              df["detected_at"] = pd.to_datetime(df["detected_at"])

→ master_df (detections_df):
  columns: [detection_id, detected_at, area_id, area_name, area_type,
            product_id, product_name, product_code, product_color, product_weight,
            line_id, line_name, line_code]
  shape:   (N, 13)
```

---

## FASE 10 — FETCH Y CÁLCULO DE DOWNTIME

```
_build_context() → downtime_service.get_downtime(
                       session, line_ids, cleaned, detections_df)
  │
  │─── STEP 10.1: DB DOWNTIME ────────────────────────────────────
  │
  ├── _fetch_db_events(session, line_ids, cleaned)
  │     └── downtime_repository.fetch_downtime_multi_line(
  │               session, line_ids, cleaned)
  │           │
  │           └── para cada line_id:
  │                 table_name = table_resolver.downtime_table(line_id)
  │                   → "downtime_events_tecmar1"
  │                 │
  │                 fetch_downtime(session, table_name, cleaned)
  │                   └── LOOP cursor-paginated:
  │                         sql = query_builder.build_downtime_query(
  │                             table_name, cleaned, cursor_id, limit=10_000)
  │                         # SELECT event_id, last_detection_id,
  │                         #   start_time, end_time,
  │                         #   TIMESTAMPDIFF(SECOND, start_time, end_time) AS duration_seconds,
  │                         #   reason_code, reason, is_manual, created_at
  │                         # FROM downtime_events_tecmar1
  │                         # WHERE event_id > :cursor_id
  │                         #   AND start_time BETWEEN :date_from AND :date_to
  │                         # ORDER BY event_id LIMIT 10000
  │                 df["line_id"] = line_id
  │           concat → db_df
  │     │
  │     └── _normalize_db_columns(db_df)
  │           rename "duration_seconds" → "duration"
  │           df["source"] = "db"      ← marca origen
  │
  │─── STEP 10.2: CALCULAR GAP DOWNTIME ──────────────────────────
  │
  ├── _calculate_gap_events(detections_df, line_ids, threshold_override)
  │     └── downtime_calculator.calculate_gap_downtimes(
  │               detections_df, line_ids)
  │           │
  │           └── para cada line_id:
  │                 threshold = metadata_cache.get_production_lines()
  │                             [line_id]["downtime_threshold"]  (segundos)
  │                 df_line = detections_df[detections_df.line_id == line_id]
  │                 df_line.sort_values("detected_at")
  │                 │
  │                 for i in range(1, len(df_line)):
  │                   gap = detected_at[i] - detected_at[i-1]
  │                   if gap > threshold:
  │                     [acumula gaps consecutivos → 1 evento]
  │                     emit { start_time, end_time, duration,
  │                            reason_code: None, line_id,
  │                            source: "calculated" }
  │           → calc_df
  │
  │─── STEP 10.3: DE-DUPLICAR (DB GANA) ──────────────────────────
  │
  ├── remove_overlapping(calc_df, db_df)
  │     └── para cada evento calculado:
  │           line_db = db_df[db_df.line_id == calc.line_id]
  │           overlaps = (calc.start < line_db.end) & (calc.end > line_db.start)
  │           si ANY overlap → descartar el calculado (DB tiene prioridad)
  │     → calc_df depurado
  │
  │─── STEP 10.4: MERGE + ENRICH ─────────────────────────────────
  │
  └── _merge_and_enrich(db_df, calc_df)
        ├── merged = pd.concat([db_df, calc_df])
        ├── to_datetime(start_time, end_time)
        ├── sort_values("start_time")
        └── _enrich(merged)
              lines = metadata_cache.get_production_lines()
              df["line_name"] = df["line_id"].map(...)
              df["duration"]  = pd.to_numeric(df["duration"])

→ downtime_df:
  columns: [event_id, start_time, end_time, duration, reason_code,
            reason, is_manual, line_id, line_name, source]
  source values: "db" | "calculated"
```

---

## FASE 11 — CONTEXTO DE DATOS CONSTRUIDO

```
_build_context() → retorna DashboardContext(
    detections  = master_df,     # N detecciones enriquecidas
    downtime    = downtime_df,   # M paradas (DB + calculadas)
    cleaned     = {...},         # filtros validados
    line_ids    = [1, 2],
    widget_names = ["KpiTotalProduction", "ProductionTimeChart",
                    "DowntimeTable", "KpiOee", ...],
    widget_catalog = {1: {widget_name: "KpiTotalProduction"}, ...}
)
```

---

## FASE 12 — EJECUCIÓN DE WIDGETS

```
pipeline.py → _execute_widgets(ctx)
  └── widget_engine.process_widgets(
          widget_names  = ctx.widget_names,
          detections_df = ctx.detections,
          downtime_df   = ctx.downtime,
          lines_queried = ctx.line_ids,
          cleaned       = ctx.cleaned,
          widget_catalog = ctx.widget_catalog,
      )
        │
        └── para cada class_name en widget_names:
              _process_single(class_name, ...)
```

### Por cada widget — _process_single():

```
class_name = "ProductionTimeChart"
  │
  ├── STEP A: AUTO-DISCOVERY de la clase
  │     _resolve_class("ProductionTimeChart")
  │       ├── camel_to_snake("ProductionTimeChart") → "production_time_chart"
  │       ├── importlib.import_module(
  │       │       "new_app.services.widgets.types.production_time_chart")
  │       └── getattr(module, "ProductionTimeChart")
  │             → clase ProductionTimeChart (se cachea en _class_cache)
  │
  ├── STEP B: RESOLVER ID y NOMBRE
  │     _resolve_catalog_info("ProductionTimeChart", widget_catalog)
  │       → (widget_id=5, display_name="Producción en el tiempo")
  │
  ├── STEP C: SCOPING de datos
  │     _scope_data(ProductionTimeChart, detections_df)
  │       ├── required_columns = ["detected_at", "area_type",
  │       │                        "line_id", "product_name", "product_color"]
  │       └── df = detections_df[required_columns]
  │             (solo las columnas que el widget necesita)
  │
  ├── STEP D: CONSTRUIR WidgetContext
  │     ctx = WidgetContext(
  │         widget_id    = 5,
  │         widget_name  = "ProductionTimeChart",
  │         display_name = "Producción en el tiempo",
  │         data         = scoped_df,        ← solo columnas necesarias
  │         downtime     = downtime_df,      ← compartido, sin scoping
  │         lines_queried = [1, 2],
  │         params       = cleaned,
  │         config       = {"curve_type": "smooth"},  ← default_config
  │     )
  │
  └── STEP E: EJECUTAR widget.process()
        widget = ProductionTimeChart(ctx)
        result = widget.process()
          │
          ├── df = self.df  (scoped detections)
          ├── interval, curve_type, show_downtime = self.ctx.params...
          │
          ├── df["detected_at"] = pd.to_datetime(...)
          ├── full_index = pd.date_range(date_from, date_to, freq="H")
          │
          ├── global_series = df.resample("H").size()
          │                     .reindex(full_index, fill_value=0)
          │
          ├── labels = format_time_labels(global_series.index, "hour")
          │
          ├── _build_datasets(df, products, global_series, freq, curve_type)
          │     └── para cada product:
          │           series = df[product].resample("H").size()
          │           datasets.append({ label, data, borderColor,
          │                             backgroundColor, tension... })
          │
          ├── _build_class_details(df, freq, "hour")
          │     └── grouped = df.groupby([Grouper("H"), "product_name"]).size()
          │         → { "14/02 10:00": { "Prod A": 45, "Prod B": 12 } }
          │
          ├── _build_downtime_overlay(show_downtime, global_series)
          │     └── para cada evento en downtime_df:
          │           source = evt["source"]
          │           si source=="calculated" and not show_downtime: skip
          │           start_idx = find_nearest_label_index(labels, evt_start)
          │           end_idx   = find_nearest_label_index(labels, evt_end)
          │           reason = incidents.get(reason_code)["description"]
          │           visual_type = "db_confirmed"|"db_unconfirmed"|"calculated"
          │           events.append({ xMin, xMax, duration_min,
          │                           has_incident, source, visual_type... })
          │
          └── retorna WidgetResult(
                  widget_id   = 5,
                  widget_name = "ProductionTimeChart",
                  widget_type = "chart",
                  data = {
                    labels:          ["10:00", "11:00", ...],
                    datasets:        [{label, data, color...}],
                    curve_type:      "smooth",
                    class_details:   {...},
                    downtime_events: [{xMin, xMax, ...}],
                    show_downtime:   false,
                  },
                  metadata = { category: "chart", total_points: 24,
                               downtime_count: 3 }
              ).to_dict()

[Se repite para cada widget: KpiTotalProduction, DowntimeTable, KpiOee, ...]
```

---

## FASE 13 — ENSAMBLADO DE RESPUESTA

```
pipeline.py → ResponseAssembler.assemble(ctx, widgets_result, elapsed,
                  raw_df=ctx.detections, downtime_df=ctx.downtime)
  │
  ├── _index_widgets(widgets_result)
  │     → { "5": {widget_id:5, widget_name:..., data:{...}},
  │          "1": {...}, ... }
  │       (indexado por widget_id como string)
  │
  ├── _extract_period(ctx.cleaned)
  │     → { start: "2026-02-01", end: "2026-02-13" }
  │
  ├── metadata = {
  │       total_detections:    len(ctx.detections),
  │       total_downtime_events: len(ctx.downtime),
  │       lines_queried:       [1, 2],
  │       is_multi_line:       True,
  │       widget_count:        N,
  │       period:              { start, end },
  │       interval:            "hour",
  │       elapsed_seconds:     1.234,
  │       timestamp:           "2026-02-13T14:35:00",
  │   }
  │
  ├── [include_raw=True] →
  │     raw_data     = _serialize_detections(raw_df)
  │       └── selecciona _RAW_DETECTION_COLS, convierte timestamps a ISO strings
  │     raw_downtime = _serialize_downtime(downtime_df)
  │       └── selecciona _RAW_DOWNTIME_COLS, convierte timestamps a ISO strings
  │     metadata["shift_windows"] = _build_shift_windows()
  │       └── metadata_cache.get_shifts() → { "1": {name, start, end,
  │                                                  planned_seconds, is_overnight} }
  │     metadata["line_config"] = _build_line_config([1,2])
  │       └── metadata_cache.get_production_lines() → { "1": {line_name,
  │                                                            availability,
  │                                                            performance} }
  │
  └── retorna {
        "widgets":      { "1": {...}, "5": {...}, ... },
        "metadata":     { total_detections, period, shift_windows, line_config... },
        "raw_data":     [ {detected_at, line_id, area_type, product_name...} ],
        "raw_downtime": [ {start_time, end_time, duration, source, ...} ]
      }

→ FastAPI serializa el dict a JSON y lo envía como respuesta HTTP 200
```

---

## FASE 14 — FRONTEND RECIBE Y PROCESA LA RESPUESTA

```
DashboardOrchestrator.applyFilters(ctx) [continuación en JS]
  │
  ├── result = await DashboardAPI.fetchDashboardData(...)  ← response JSON
  │
  ├── ctx._rawData      = result.raw_data
  ├── ctx._rawDowntime  = result.raw_downtime
  ├── ctx._shiftWindows = result.metadata.shift_windows
  ├── ctx._lineConfig   = result.metadata.line_config
  │
  ├── ctx.queryMetadata = {
  │       total_detections: result.metadata.total_detections,
  │       elapsed_ms:       performance.now() - startTime,
  │   }
  │
  ├── ctx.isMultiLine    = result.metadata.is_multi_line
  │
  ├── ChartRenderer.destroyAll(ctx.chartInstances)
  │     └── para cada canvas en chartInstances:
  │           Alpine.raw(chart).destroy()   ← destruye instancia Chart.js
  │
  ├── ctx._renderedTabs = new Set()          ← reset lazy loading
  ├── ctx.widgetResults = result.widgets     ← Alpine reactivity: re-render
  ├── ctx.hasData       = true
  ├── ctx.filtersApplied = true
  ├── ctx.filterCount   = _countActiveFilters(ctx.params)
  ├── ctx.lastUpdate    = new Date().toLocaleTimeString()
  │
  └── _renderTabCharts(ctx, ctx.activeTab)   ← LAZY: solo tab activa
```

---

## FASE 15 — RENDER DE WIDGETS (Alpine.js reactivity)

```
ctx.widgetResults = result.widgets    ← dispara Alpine reactivity
  │
  └── Alpine re-evalúa todos los x-show, x-text, x-for en el DOM:
  
        Para widgets KPI (_widget_kpi.html):
          x-show="widgetResults['1']?.data"  → true → muestra card
          x-text="widgetResults['1']?.data?.value"   → "1,245"
          x-text="widgetResults['1']?.data?.unit"    → "uds"
  
        Para widgets Table (_widget_table.html):
          x-for="col in widgetResults['3']?.data?.columns"  → renderiza headers
          x-for="row in widgetResults['3']?.data?.rows"     → renderiza filas
          x-if="col.key === 'source_badge'"  → badge de color (verde/naranja/rojo)
  
        Para widgets Chart (_widget_chart.html):
          <canvas id="chart-5"></canvas>   → canvas vacío en DOM
```

---

## FASE 16 — RENDER DE GRÁFICOS (Chart.js)

```
DashboardOrchestrator._renderTabCharts(ctx, "produccion")
  │
  ├── Filtra widgets de la tab "produccion"
  │     widgetMeta.filter(w => w.tab === "produccion")
  │     → [{widget_id:5, widget_name:"ProductionTimeChart"}, ...]
  │
  └── requestAnimationFrame → requestAnimationFrame
        (doble rAF: espera que Alpine haga visible el DOM)
        │
        └── para cada chartWidget:
              ChartRenderer.render(
                  chartType   = "line_chart",
                  widgetData  = ctx.widgetResults["5"],
                  chartInstances,
                  isMultiLine = false,
                  mode        = "line"
              )
                │
                ├── canvasId = "chart-5"
                ├── canvas = document.getElementById("chart-5")
                │
                ├── [si canvas no visible] → retry hasta 10 veces (60ms cada uno)
                │
                ├── ChartConfigBuilder.getConfig("line_chart", data, resetBtn, isMultiLine, "line")
                │     └── buildLineConfig(data, resetBtn, isMultiLine, "line")
                │           ├── curveType = data.curve_type   → "smooth"
                │           ├── stacked   = false
                │           ├── labels    = data.labels        → ["10:00", "11:00"...]
                │           ├── datasets  = data.datasets      → [{label, data, color}]
                │           │
                │           ├── buildZoomPlugin(resetBtn)
                │           │     → { pan: {enabled}, zoom: {wheel, pinch}, limits }
                │           │
                │           ├── buildDowntimeAnnotations(data.downtime_events)
                │           │     └── para cada evt:
                │           │           vtype = evt.visual_type
                │           │           bg/bdr/lc/lb = colores según vtype:
                │           │             "db_confirmed"   → verde  (CSS vars)
                │           │             "db_unconfirmed" → naranja
                │           │             "calculated"     → rojo
                │           │           annotations["dt_0"] = {
                │           │             type: 'box', xMin, xMax,
                │           │             backgroundColor: bg,
                │           │             label: { content: "✓ 15min" }
                │           │           }
                │           │
                │           └── retorna config completo Chart.js
                │
                ├── new Chart(canvas.getContext('2d'), config)
                │     → Chart.js renderiza el gráfico en el canvas
                │
                └── chartInstances["chart-5"] = chart   ← guardado para destruir luego
```

---

## FASE 17 — USUARIO VE LOS WIDGETS CON DATOS

```
Estado final del Browser:
  ✓ KPIs mostrando valores (producción total, OEE, disponibilidad...)
  ✓ Gráfico de línea con datos por hora y anotaciones de paradas:
      · Verde   → paradas registradas con motivo confirmado
      · Naranja → paradas registradas sin motivo
      · Rojo    → paradas calculadas (solo si show_downtime=true)
  ✓ Tabla de paradas con columnas Tipo/Origen con badges de color
  ✓ Barra de estado: "1,245 detecciones · 842ms"
  ✓ Timestamp de última actualización
```

---

## FLUJO DE CAMBIO DE TAB (Lazy Loading)

```
Usuario: click en tab "OEE"
  │
  ▼
Template: @click="activeTab='oee';
           $nextTick(() => DashboardOrchestrator.onTabChange($data))"
  │
  ├── Alpine: activeTab = 'oee'
  │     → x-show re-evalúa → los widgets de 'oee' aparecen en DOM
  │       los widgets de 'produccion' se ocultan (display:none)
  │
  └── DashboardOrchestrator.onTabChange(ctx)
        ├── ctx._renderedTabs.has("oee") → false → continuar
        └── _renderTabCharts(ctx, "oee")
              ├── filtra widgets de tab "oee"
              └── requestAnimationFrame → requestAnimationFrame
                    → ChartRenderer.render para cada chart de "oee"
                    → ctx._renderedTabs.add("oee")

[Segundo click en tab "OEE":]
  └── onTabChange(ctx)
        └── ctx._renderedTabs.has("oee") → true → noop (ya renderizado)
```

---

## FLUJO DE RE-QUERY (Cambio de Filtros)

```
Usuario: cambia fechas/línea → click "Aplicar"
  │
  ▼
DashboardOrchestrator.applyFilters(ctx)
  ├── ChartRenderer.destroyAll()     ← destruye TODOS los charts existentes
  ├── ctx._renderedTabs = new Set()  ← resetea lazy loading
  ├── [Fases 5 a 16 se repiten completas]
  └── _renderTabCharts(ctx, activeTab)  ← solo renderiza tab activa
```

---

## MAPA DE ARCHIVOS POR FASE

```
FASE 1  Login           routes/auth.py → core/auth.py → core/jwt_utils.py
FASE 2  HTML Shell      routes/dashboard.py → api/v1/layout.py
                        → api/v1/filters.py → config/widget_layout.py
FASE 3  JS Init         static/js/dashboard-app.js
FASE 4  Filtros UI      static/js/dashboard-app.js (Alpine x-model)
FASE 5  Validación      static/js/dashboard-orchestrator.js
                        → api/v1/filters.py → services/filters/engine.py
FASE 6  Request         static/js/dashboard-orchestrator.js
                        → static/js/api-client.js
FASE 7  Endpoint        api/v1/dashboard.py → api/v1/dependencies.py
FASE 8  Orchestrator    services/orchestrator/pipeline.py
                        → services/filters/engine.py
                        → services/data/line_resolver.py
                        → services/orchestrator/resolver.py
FASE 9  Detecciones     services/data/detection_service.py
                        → services/data/detection_repository.py
                        → services/data/query_builder.py
                        → services/data/enrichment.py
FASE 10 Downtime        services/data/downtime_service.py
                        → services/data/downtime_repository.py
                        → services/data/downtime_calculator.py
FASE 11 Contexto        services/orchestrator/context.py (DashboardContext)
FASE 12 Widgets         services/widgets/engine.py (WidgetEngine)
                        → services/widgets/types/*.py (18 widgets)
FASE 13 Ensamblado      services/orchestrator/assembler.py
FASE 14 JS Recibe       static/js/dashboard-orchestrator.js
FASE 15 Alpine Render   templates/dashboard/partials/widgets/_widget_*.html
FASE 16 Charts          static/js/chart-renderer.js → static/js/chart-config.js
FASE 17 Resultado       Browser muestra widgets con datos
```