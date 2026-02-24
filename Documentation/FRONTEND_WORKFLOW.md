# Workflow del Frontend: Filtros y Widgets

Esta documentación detalla la arquitectura modular y el flujo de trabajo (workflow) del Dashboard, explicando paso a paso cómo interacciona el frontend (Alpine.js + Chart.js) con el backend (FastAPI), cómo se procesan y validan los filtros, y cómo se renderizan y re-calculan los widgets.

---

## 1. Arquitectura General y Arranque (Bootstrap)

La arquitectura no funciona como una SPA (Single Page Application) tradicional. Utiliza **Server-Side Rendering híbrido**:
1. El backend de Flask (a través de [routes/dashboard.py](file:///c:/Users/herna/OneDrive/Desktop/Dashboard/new_app/routes/dashboard.py)) determina la estructura de la página leyendo del registro de componentes las clases habilitadas.
2. Estos componentes y sus metadatos (IDs reales, variables de configuración) se inyectan en el HTML resultante como un bloque JSON seguro (`<script type="application/json" id="dashboard-config">`).
3. **Alpine.js** arranca (ejecutando [init()](file:///c:/Users/herna/OneDrive/Desktop/Dashboard/new_app/static/js/dashboard-app.js#110-115)) leyendo el HTML y este JSON, creando su estado reactivo local ([filters](file:///c:/Users/herna/OneDrive/Desktop/Dashboard/new_app/core/cache.py#253-255), [widgets](file:///c:/Users/herna/OneDrive/Desktop/Dashboard/new_app/services/orchestrator/assembler.py#155-162), [params](file:///c:/Users/herna/OneDrive/Desktop/Dashboard/new_app/api/v1/dashboard.py#114-143) iniciales).

---

## 2. Workflow de los Filtros

El flujo de un filtro atraviesa múltiples pasos desde que el usuario lo visualiza hasta que consulta datos:

### A. Registro y Renderizado HTML
1. Un filtro se define extendiendo [BaseFilter](file:///c:/Users/herna/OneDrive/Desktop/Dashboard/new_app/services/filters/base.py#85-152) en Python y se habilita en `dashboard_template`.
2. El archivo Jinja [_filters_panel.html](file:///c:/Users/herna/OneDrive/Desktop/Dashboard/new_app/templates/dashboard/partials/_filters_panel.html) itera sobre la lista de filtros aprobados del backend y llama al sub-template correspondiente según `filter_type` (ej: [_filter_dropdown.html](file:///c:/Users/herna/OneDrive/Desktop/Dashboard/new_app/templates/dashboard/partials/filters/_filter_dropdown.html) o [_filter_multiselect.html](file:///c:/Users/herna/OneDrive/Desktop/Dashboard/new_app/templates/dashboard/partials/filters/_filter_multiselect.html)).
3. Cada input de HTML se enlaza (bind) al objeto de Alpine.js: `x-model="params.line_id"`.

### B. Funciones y Manejadores (Handlers) en Alpine.js
Cuando el usuario interactúa, dispara handlers del state manager del Dashboard:
- **[toggleMultiselect(param, value)](file:///c:/Users/herna/OneDrive/Desktop/Dashboard/new_app/static/js/dashboard-app.js#135-146)**: Para checkboxes (ej: productos o áreas). Agrega o quita el valor de un array. Eventualmente llama a [onProductIdsChange()](file:///c:/Users/herna/OneDrive/Desktop/Dashboard/new_app/static/js/dashboard-app.js#417-428).
- **[onLineChange(rawValue)](file:///c:/Users/herna/OneDrive/Desktop/Dashboard/new_app/static/js/dashboard-app.js#147-176)**: Maneja la reacción en cadena (Cascading). Si elige una línea, solicita por [fetch](file:///c:/Users/herna/OneDrive/Desktop/Dashboard/new_app/routes/dashboard.py#84-104) las Áreas habilitadas de esa línea para poblar el filtro hijo (`DashboardAPI.fetchAreas`).
- **Validaciones Automáticas**: Funciones como [validateEndDate()](file:///c:/Users/herna/OneDrive/Desktop/Dashboard/new_app/static/js/dashboard-app.js#116-125) corrigen tiempos y evitan que la fecha final sea menor a la inicial.

### C. Solicitud (Execution Workflow)
Al presionar el botón "Aplicar" (o dispararse funciones debounce para interval/shift):
1. **Normalización (`FilterUtils.normalizeParams`)**: Convierte strings vacíos en `null` para el parseo Pydantic en backend.
2. **Validación Previa (`DashboardAPI.validateFilters`)**: Hace un `POST /api/v1/filters/validate`. Si algo arroja error, usa la función [_showFilterError()](file:///c:/Users/herna/OneDrive/Desktop/Dashboard/new_app/static/js/dashboard-app.js#509-522) para inyectar y renderizar un mensaje temporario.
3. **Ejecución (`DashboardAPI.fetchDashboardData`)**: Arma el Request Body dinámico con los valores validados y exige `include_raw = true` para que vuelva la data pura requerida por la "Etapa 3".

---

## 3. Workflow de los Widgets y Client-Side Re-Query (Etapa 3)

El objetivo de la Etapa 3 reduce llamadas repetitivas al backend al re-filtrar resultados puramente en el cliente si es posible.

### A. Estructura y Template HTML
1. Al igual que los filtros, los contenedores gráficos vacíos (`<canvas>` o `<table>`) son dibujados por Flask en [_main_content.html](file:///c:/Users/herna/OneDrive/Desktop/Dashboard/new_app/templates/dashboard/partials/_main_content.html) con atributos CSS Grid calculados.
2. Se utiliza el motor `Chart.js` (gobernado por [chart-renderer.js](file:///c:/Users/herna/OneDrive/Desktop/Dashboard/new_app/static/js/chart-renderer.js)).

### B. Distribución de Resultados
1. Cuando la API resuelve el bloque principal de datos, llena las variables de estado reactivo:
   - `widgetResults` (Datos calculados finales)
   - `_rawData` + `_rawDowntime` (Materia prima y búfers de validación rápida).
2. Función **[_renderAllCharts()](file:///c:/Users/herna/OneDrive/Desktop/Dashboard/new_app/static/js/dashboard-app.js#283-318)**: Itera sobre los `widgetResults`, encuentra sus configuraciones en base al catálogo y delega el dibujo delegando en `ChartRenderer.render(...)`.
3. Alpine.js usa un "Doble-Request-AnimationFrame" para garantizar que la transición visual de mostrar un `<canvas>` oculto termine antes de que Chart.js pida sus dimensiones calculadas.

### C. Client-Side Re-Aggregation (`DataEngine.js`)
Si el usuario modifica el filtro de "Intervalo", "Turno (Shift)" o "Productos", **no llama a la API**.
Llama a **`DashboardDataEngine.recompute()`**:
1. Clona `_rawData`.
2. Llama a [sliceByShiftWindow()](file:///c:/Users/herna/OneDrive/Desktop/Dashboard/new_app/static/js/dashboard-app.js#580-590) descartando eventos fuera de la hora.
3. Ejecuta [_recomputeWidget(widgetName, ...)](file:///c:/Users/herna/OneDrive/Desktop/Dashboard/new_app/static/js/dashboard-app.js#631-805) con funciones switch puras que recalculan los KPI, rankings y series temporales (con [_groupByInterval()](file:///c:/Users/herna/OneDrive/Desktop/Dashboard/new_app/static/js/dashboard-app.js#606-630)) en Javascript puro.
4. Actualiza `widgetResults` reactivamente y fuerza un [destroyAll()](file:///c:/Users/herna/OneDrive/Desktop/Dashboard/new_app/static/js/chart-renderer.js#423-430) seguido de redibujo ([_renderAllCharts](file:///c:/Users/herna/OneDrive/Desktop/Dashboard/new_app/static/js/dashboard-app.js#283-318)).

---

## 4. Cómo expandir el Dashboard

### ¿Cómo agregar un nuevo Filtro?
1. **Backend Python:** Crear una nueva clase heredera de [BaseFilter](file:///c:/Users/herna/OneDrive/Desktop/Dashboard/new_app/services/filters/base.py#85-152) en `new_app/services/filters/types/`. Defines tu `param_name` y `filter_type` (ej: `my_dropdown`).
2. **Backend HTML:** Modificar `_filters_panel.html` en caso de requerir un template `_filter_my_dropdown.html` especial. 
3. Habilitar la variable a interceptarse agregándola a `initialParams` o `_buildRequestBody()` en `new_app/static/js/dashboard-app.js`.
4. Darlo de alta en tu script o SQL en `dashboard_template`.

## 4. Path de Llamadas (End-to-End Workflow)

A continuación se detalla exactamente qué funciona y qué API se ejecuta secuencialmente desde que el usuario inicia sesión hasta que ve el gráfico renderizado.

### 4.1 Login y Generación del HTML Shell
1. **`POST /api/v1/auth/login` (FastAPI)**: El usuario envía credenciales. Retorna un JWT (`access_token`).
2. **`POST /login` (Flask)**: El frontend web llama internamente al backend. Toma el JWT y lo guarda en la cookie HTTPOnly `session`. El usuario es redirigido a `/dashboard`.
3. **`GET /dashboard/` (`routes/dashboard.py` - Flask)**:
   - Extrae el `tenant_id` y `role` de la sesión del usuario.
   - Ejecuta `_fetch_layout(api_base, tenant_id, role)` → llama internamente a **`GET /api/v1/layout/config?tenant_id=X&role=Y`**. Esto lee la base MySQL `dashboard_template` y retorna IDs habilitados.
   - Ejecuta `_fetch_filters(api_base, enabled_filter_ids)` → llama a **`GET /api/v1/filters/?filter_ids=X,Y...`**.
   - Ejecuta `_enrich_widgets(widgets_data)` → Cruza cada nombre de widget con `WIDGET_LAYOUT` en `new_app/config/widget_layout.py` para obtener estilo de grilla (`col_span`).
4. **Jinja2 Render (`index.html`)**: El HTML se construye. El layout se convierte en DOM y las variables se incrustan en `<script type="application/json" id="dashboard-config">`.

### 4.2 Inicialización Javascript
1. **`dashboardApp.init()` (Alpine.js)**:
   - Se ejecuta el script. Parsea el DOM buscando `#dashboard-config`.
   - Lee `config.filters` y calcula `initialParams` con los `default_value` definidos en backend.
   - Asigna un Watch a los combos desplegables y checkboxes a través de `x-model`.
   - Llama inicialmente de manera asíncrona a `applyFilters()`.

### 4.3 Petición de Data y Renderizado Visual
1. **Validación (`dashboardApp.applyFilters()`)**:
   - `fetch(apiBase + '/api/v1/filters/validate')` -> Dispara **`POST /api/v1/filters/validate` (FastAPI)** → Pasa por `filter_engine.validate_input` asegurando que todos los diccionarios cumplan los esquemas Pydantic requeridos (Fechas correctas, arrays de ints).
2. **Consultar API Principal (`dashboardApp.applyFilters()`)**:
   - `fetch(dashboardApiUrl, {body: ...})` -> Dispara **`POST /api/v1/dashboard/data` (FastAPI)**.
   - Entra en `DashboardOrchestrator.execute()`.
   - Resuelve Instancias: Pasa los parámetros a los 10 Filtros (en `filters/types/*.py`) y extrae cláusulas SQL.
   - DataBroker: Hace la query gigante en MySQL usando las cláusulas en `downtime_service` y `metrics_service`, y retorna los diccionarios limpios.
   - WidgetEngine: Carga las clases de `widgets/types/*.py` e inyecta la data fresca devolviendo JSON estructurado.
3. **Armado del Objeto (`dashboard-app.js`)**:
   - Se reciben `widgetResults`, `_rawData`, `_rawDowntime`.
   - Se destruyen gráficos viejos con `ChartRenderer.destroyAll()`.
4. **Pintado en Canvas (`ChartRenderer.render()`)**:
   - `_renderAllCharts` usa `CHART_TYPE_MAP` para mapear el widget (Ej: `ProductionTimeChart` -> `line_chart`).
   - Llama a `ChartRenderer.render('line_chart', data...)`.
   - `_configBuilders['line_chart']` ejecuta `buildLineConfig()` devolviendo el dict que la librería Chart.js necesita para renderizar líneas con tooltips interpolados, barras o puntos de dispersión de ChartJS interno.

---

## 5. Configuración de Base de Datos para Nuevos Componentes

Si vas a agregar nuevos componentes al proyecto, además de crear los archivos `.py` (como indica la sección 4) tenes que darlos de alta en la base MySQL del entorno global, ya que el API utiliza estas tablas para determinar qué tiene cada *"Tenant"* (Cliente/Empresa).

### Para un Filtro Nuevo
En la tabla `filter`:
```sql
INSERT INTO filter (filter_name, display_order) 
VALUES ('MiFiltro', 11);
-- filter_name DEBE ser el nombre exacto de tu clase Python en CamelCase (ej: 'MiFiltroNuevo')
```

### Para un Widget Nuevo
En la tabla `widget_catalog`:
```sql
INSERT INTO widget_catalog (widget_name, description) 
VALUES ('MyNewChartWidget', 'Muestra algo muy util');
-- widget_name DEBE ser el nombre exacto de la clase Python (ej: 'MyNewChartWidget')
```

### Para Habilitarlo a un Cliente y Rol
En la tabla `dashboard_template`:
El Dashboard está regido por roles. A un cliente (ej tenant `2`) se le habilita una plantilla JSON específica en la columna `layout_config`.
```sql
UPDATE dashboard_template 
SET layout_config = '{
  "enabled_widget_ids": [1, 2, 3, 4, /* NUEVO_WIDGET_ID */],
  "enabled_filter_ids": [1, 2, 3, 4, /* NUEVO_FILTER_ID */]
}'
WHERE tenant_id = 2 AND role_access = 'admin_cn';
```
*(Para verificar los IDs de las tablas usa un Auto-Increment, con lo cual debes verificar qué ID le tocó a tu widget/filtro nuevo).*
