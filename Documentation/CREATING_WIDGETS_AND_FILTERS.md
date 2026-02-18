# Guía Completa: Creación de Widgets y Filtros

> **Proyecto:** Dashboard SaaS Multi-Tenant  
> **Stack:** FastAPI + Flask + Alpine.js + Chart.js + Tailwind CSS  
> **Última actualización:** Etapa 7

---

## Tabla de Contenidos

1. [Arquitectura General](#1-arquitectura-general)
2. [Creación de Widgets](#2-creación-de-widgets)
   - [Pipeline completo](#21-pipeline-completo-de-un-widget)
   - [Paso 1 — Clase Python](#22-paso-1--crear-la-clase-del-widget)
   - [Paso 2 — WIDGET_REGISTRY](#23-paso-2--registrar-en-widget_registry)
   - [Paso 3 — WIDGET_RENDER_MAP](#24-paso-3--registrar-en-widget_render_map)
   - [Paso 4 — INSERT en BD](#25-paso-4--insert-en-base-de-datos)
   - [Paso 5 — layout_config](#26-paso-5--agregar-a-layout_config)
   - [Paso 6 — Condicional: nuevo render_type](#27-paso-6-condicional--nuevo-render_type)
   - [Paso 7 — Condicional: nuevo chart_type](#28-paso-7-condicional--nuevo-chart_type)
3. [Widgets por Categoría: Plantillas y Data Shapes](#3-widgets-por-categoría-plantillas-y-data-shapes)
   - [KPI](#31-kpi)
   - [Chart](#32-chart)
   - [Table](#33-table)
   - [Indicator](#34-indicator)
   - [Summary](#35-summary)
   - [Feed](#36-feed)
4. [Creación de Filtros](#4-creación-de-filtros)
   - [Pipeline completo](#41-pipeline-completo-de-un-filtro)
   - [Paso 1 — Clase Python](#42-paso-1--crear-la-clase-del-filtro)
   - [Paso 2 — FILTER_REGISTRY](#43-paso-2--registrar-en-filter_registry)
   - [Paso 3 — INSERT en BD](#44-paso-3--insert-en-base-de-datos)
   - [Paso 4 — layout_config](#45-paso-4--agregar-a-layout_config)
   - [Paso 5 — Condicional: nuevo filter_type](#46-paso-5-condicional--nuevo-filter_type)
5. [Filtros por Tipo: Plantillas y Ejemplos](#5-filtros-por-tipo-plantillas-y-ejemplos)
   - [DateRange](#51-daterange)
   - [Dropdown](#52-dropdown)
   - [Multiselect](#53-multiselect)
   - [Text](#54-text)
   - [Number](#55-number)
   - [Toggle](#56-toggle)
6. [Resolución Automática (Discovery)](#6-resolución-automática-discovery)
7. [Checklist Rápido](#7-checklist-rápido)

---

## 1. Arquitectura General

```
┌─────────────────────────────────────────────────────────────────────┐
│  Frontend (Flask/Jinja2 + Alpine.js + Chart.js)                     │
│                                                                     │
│  dashboard-app.js ─→ POST /api/v1/dashboard/data ──────────────────┤
│       ↑                                                             │
│       └── ChartRenderer.render(chartType, widgetData, ...)          │
│                                                                     │
│  _main_content.html  ─→ {% include partials/widgets/_widget_X.html %}│
│  _enrich_widgets()   ─→ WIDGET_RENDER_MAP → render_type, size_class │
├─────────────────────────────────────────────────────────────────────┤
│  Backend (FastAPI)                                                   │
│                                                                     │
│  DashboardOrchestrator                                               │
│    ├── FilterEngine.validate_input(params) → cleaned                │
│    ├── DataPipeline → detections_df, downtime_df                    │
│    └── WidgetEngine.process_widgets(widget_names, ...) → results    │
│                                                                     │
│  WidgetEngine:                                                       │
│    1. WIDGET_REGISTRY[class_name]    → metadata                     │
│    2. CamelCase → snake_case         → module path                  │
│    3. importlib(module).class_name   → BaseWidget subclass          │
│    4. WidgetContext + process()      → WidgetResult.to_dict()       │
│                                                                     │
│  FilterEngine:                                                       │
│    1. MetadataCache.get_filters()    → DB rows                      │
│    2. FILTER_REGISTRY[class_name]    → metadata                     │
│    3. FilterConfig merger            → config                       │
│    4. _get_filter_class(filter_type) → BaseFilter subclass          │
├─────────────────────────────────────────────────────────────────────┤
│  Base de Datos (MySQL)                                               │
│    widget_catalog   → {widget_id, widget_name, description, ...}    │
│    filter           → {filter_id, filter_name, display_order, ...}  │
│    dashboard_template → {layout_config JSON: {widgets, filters}}    │
└─────────────────────────────────────────────────────────────────────┘
```

### Archivos clave

| Archivo | Propósito |
|---------|-----------|
| `new_app/config/widget_registry.py` | `WIDGET_REGISTRY` + `WIDGET_RENDER_MAP` + `WIDGET_SIZE_CSS` |
| `new_app/config/filter_registry.py` | `FILTER_REGISTRY` |
| `new_app/services/widgets/base.py` | `BaseWidget`, `WidgetContext`, `WidgetResult` |
| `new_app/services/widgets/engine.py` | `WidgetEngine` — resolución dinámica CamelCase→snake_case |
| `new_app/services/filters/base.py` | `BaseFilter`, `OptionsFilter`, `InputFilter`, `FilterConfig` |
| `new_app/services/filters/engine.py` | `FilterEngine` — instanciación dinámica por `filter_type` |
| `new_app/services/widgets/types/` | Clases concretas de widgets (1 archivo = 1 widget) |
| `new_app/services/filters/types/` | Clases concretas de filtros (1 archivo = 1 filter_type) |
| `new_app/routes/dashboard.py` | `_enrich_widgets()` — inyecta metadata frontend |
| `new_app/static/js/chart-renderer.js` | `ChartRenderer` — builders Chart.js por chart_type |
| `new_app/static/js/dashboard-app.js` | `dashboardApp()` — Alpine.js, CHART_TYPE_MAP |
| `new_app/templates/dashboard/partials/_main_content.html` | Grid de widgets, branching por render_type |
| `new_app/templates/dashboard/partials/widgets/` | Partials HTML por render_type |

---

## 2. Creación de Widgets

### 2.1 Pipeline completo de un widget

```
Paso 1 ── Crear clase Python en services/widgets/types/
       │
Paso 2 ── Agregar entrada en WIDGET_REGISTRY
       │
Paso 3 ── Agregar entrada en WIDGET_RENDER_MAP
       │
Paso 4 ── INSERT en tabla widget_catalog (BD tenant)
       │
Paso 5 ── Agregar widget_id al layout_config en dashboard_template
       │
       ├── Paso 6 (CONDICIONAL) ── Si el render_type es NUEVO:
       │     ├── Crear partial HTML en partials/widgets/
       │     └── Agregar branch en _main_content.html
       │
       └── Paso 7 (CONDICIONAL) ── Si el chart_type es NUEVO:
             ├── Agregar builder en chart-renderer.js
             └── Agregar mapping en CHART_TYPE_MAP (dashboard-app.js)
```

> **Pasos 1-5 son SIEMPRE obligatorios.**  
> **Pasos 6-7 son condicionales** — solo si introduces un nuevo tipo de renderizado o gráfico que no exista.

### Tipos existentes (no requieren Paso 6):

| `render_type` | Partial existente | Descripción |
|---------------|-------------------|-------------|
| `kpi` | `_widget_kpi.html` | Tarjeta KPI con valor + unidad |
| `kpi_oee` | `_widget_kpi.html` | KPI con breakdown availability/performance/quality |
| `chart` | `_widget_chart.html` | Canvas Chart.js (requiere `chart_type`) |
| `table` | `_widget_table.html` | Tabla scrollable con paginación |
| `indicator` | `_widget_indicator.html` | Tarjetas de estado de línea |
| `summary` | `_widget_summary.html` | Grid de métricas |
| `feed` | `_widget_feed.html` | Lista cronológica de eventos |

### Tipos de chart existentes (no requieren Paso 7):

| `chart_type` | Builder existente | Tipo Chart.js |
|--------------|-------------------|---------------|
| `line_chart` | `buildLineConfig()` | line |
| `bar_chart` | `buildBarConfig()` | bar |
| `pie_chart` | `buildPieConfig()` | doughnut |
| `comparison_bar` | `buildBarConfig()` | bar |
| `scatter_chart` | `buildScatterConfig()` | scatter |

---

### 2.2 Paso 1 — Crear la clase del widget

**Archivo:** `new_app/services/widgets/types/{snake_case_name}.py`

> **IMPORTANTE:** El nombre del archivo DEBE ser la conversión CamelCase → snake_case del nombre de clase.  
> El `WidgetEngine` resuelve automáticamente: `KpiTotalProduction` → `kpi_total_production.py`

#### Regla de conversión:
```
KpiTotalProduction   → kpi_total_production
ProductionTimeChart  → production_time_chart
DowntimeTable        → downtime_table
LineStatusIndicator  → line_status_indicator
```

Cada carácter mayúscula (excepto el primero) inserta un `_` antes.

#### Plantilla base:

```python
"""Descripción breve del widget."""

from new_app.services.widgets.base import BaseWidget, WidgetResult


class MiNuevoWidget(BaseWidget):
    """
    Widget que hace X.
    
    Data shape retornada:
        {
            "campo1": valor,
            "campo2": valor,
        }
    """

    def process(self) -> WidgetResult:
        df = self.df  # DataFrame de detecciones (pre-scoped por required_columns)
        
        if df.empty:
            return self._empty("widget_type_string")
        
        # ... lógica de procesamiento ...
        
        return self._result(
            "widget_type_string",  # Debe coincidir con el render_type del frontend
            {
                "campo1": valor,
                "campo2": valor,
            },
            category="categoria",  # metadata adicional
        )
```

#### Propiedades disponibles en `self`:

| Propiedad | Tipo | Descripción |
|-----------|------|-------------|
| `self.df` | `pd.DataFrame` | DataFrame de detecciones (scoped por `required_columns`) |
| `self.downtime_df` | `pd.DataFrame` | DataFrame de downtimes (compartido) |
| `self.has_downtime` | `bool` | `True` si hay datos de downtime |
| `self.ctx.params` | `dict` | Parámetros de filtro validados (`cleaned`) |
| `self.ctx.config` | `dict` | `default_config` del WIDGET_REGISTRY |
| `self.ctx.lines_queried` | `list[int]` | IDs de líneas consultadas |
| `self.widget_id` | `int` | ID del widget desde `widget_catalog` |
| `self.widget_name` | `str` | Nombre de clase (registry key) |
| `self.display_name` | `str` | Nombre legible desde `widget_catalog.description` |

#### Métodos helper disponibles:

| Método | Descripción |
|--------|-------------|
| `self._result(widget_type, data, **meta)` | Construye `WidgetResult` con metadata |
| `self._empty(widget_type)` | Resultado vacío estándar (`{empty: True}`) |

#### Acceso a MetadataCache (para datos enriquecidos):

```python
from new_app.core.cache import metadata_cache

# Datos disponibles:
metadata_cache.get_production_lines()   # dict[int, dict]
metadata_cache.get_production_line(id)  # dict | None
metadata_cache.get_areas()              # dict[int, dict]
metadata_cache.get_products()           # dict[int, dict]
metadata_cache.get_shifts()             # dict[int, dict]
metadata_cache.get_incidents()          # dict[int, dict]
metadata_cache.get_failures()           # dict[int, dict]
metadata_cache.get_filters()            # dict[int, dict]
```

#### Helpers de gráficos (para widgets tipo chart):

```python
from new_app.services.widgets.helpers import (
    FALLBACK_PALETTE,        # Paleta de colores por defecto
    TIME_LABEL_FORMATS,      # Formatos de etiquetas según intervalo
    alpha,                   # alpha(color_hex, opacity) → rgba string
    format_time_labels,      # Formatea DatetimeIndex a strings legibles
    get_freq,                # interval → pandas freq string
    find_nearest_label_index, # Encuentra índice más cercano en time index
    calculate_scheduled_minutes, # Calcula minutos programados del turno
    get_lines_with_input_output, # Líneas que tienen áreas input + output
)
```

---

### 2.3 Paso 2 — Registrar en WIDGET_REGISTRY

**Archivo:** `new_app/config/widget_registry.py`

Agregar una entrada al diccionario `WIDGET_REGISTRY`:

```python
WIDGET_REGISTRY: dict[str, dict] = {
    # ... widgets existentes ...
    
    "MiNuevoWidget": {
        "category": "kpi",           # "kpi" | "chart" | "table" | "ranking" |
                                     # "indicator" | "summary" | "feed"
        "source_type": "internal",   # "internal" (BD) | "external" (API externa)
        "required_columns": [        # Columnas necesarias del master DataFrame
            "area_type",             # Data Scoping: solo recibe estas columnas
            "detected_at",           # + detected_at y line_id siempre se
        ],                           #   incluyen automáticamente si existen
        "api_source_id": None,       # Clave en external_apis.yml si source_type="external"
        "default_config": {          # Config por defecto → self.ctx.config
            "unit": "unidades",
        },
    },
}
```

#### Campos del WIDGET_REGISTRY:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `category` | `str` | Categoría lógica del widget |
| `source_type` | `str` | `"internal"` → datos de BD, `"external"` → API externa |
| `required_columns` | `list[str]` | Columnas del DataFrame que necesita. Si vacío, recibe el DF completo |
| `api_source_id` | `str\|None` | Clave en `external_apis.yml` si `source_type="external"` |
| `default_config` | `dict` | Config por defecto accesible via `self.ctx.config` |

#### Columnas disponibles en el master DataFrame:

| Columna | Descripción |
|---------|-------------|
| `detected_at` | Timestamp de detección |
| `line_id` | ID de línea de producción |
| `line_name` | Nombre de la línea |
| `area_type` | `"input"` \| `"output"` \| `"discard"` |
| `area_name` | Nombre del área |
| `product_name` | Nombre del producto |
| `product_code` | Código del producto |
| `product_weight` | Peso del producto |
| `product_color` | Color CSS del producto |

---

### 2.4 Paso 3 — Registrar en WIDGET_RENDER_MAP

**Archivo:** `new_app/config/widget_registry.py`

Agregar una entrada al diccionario `WIDGET_RENDER_MAP`:

```python
WIDGET_RENDER_MAP: dict[str, dict] = {
    # ... widgets existentes ...
    
    "MiNuevoWidget": {
        "render": "kpi",              # Tipo de partial HTML a usar
        "size": "small",              # Tamaño en el grid
        # Opcionales (solo para charts):
        # "chart_type": "line_chart", # Tipo de gráfico Chart.js
        # "chart_height": "300px",    # Altura del canvas
        # "downtime_only": True,      # No mostrar en modo multi-línea
    },
}
```

#### Campos del WIDGET_RENDER_MAP:

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `render` | `str` | ✅ | Tipo de partial: `kpi`, `kpi_oee`, `chart`, `table`, `indicator`, `summary`, `feed` |
| `size` | `str` | ✅ | Tamaño grid: `small`, `medium`, `large`, `full` |
| `chart_type` | `str` | Solo charts | `line_chart`, `bar_chart`, `pie_chart`, `comparison_bar`, `scatter_chart` |
| `chart_height` | `str` | Solo charts | Altura CSS: `"250px"`, `"300px"`, etc. |
| `downtime_only` | `bool` | Opcional | Si `True`, se oculta en modo multi-línea |

#### Tamaños del grid (WIDGET_SIZE_CSS):

| Tamaño | CSS Classes | Resultado |
|--------|-------------|-----------|
| `small` | `col-span-1` | 1 columna siempre |
| `medium` | `col-span-1 xl:col-span-1` | 1 columna |
| `large` | `col-span-1 md:col-span-2` | 2 columnas desde md |
| `full` | `col-span-full` | Ancho completo |

> Grid base: `grid-cols-1 md:grid-cols-2 xl:grid-cols-3`

---

### 2.5 Paso 4 — INSERT en base de datos

**Tabla:** `widget_catalog` (en la BD del tenant: `db_client_{tenant_id}`)

```sql
INSERT INTO widget_catalog (widget_name, description, is_active)
VALUES ('MiNuevoWidget', 'Descripción visible en el UI', 1);

-- Anotar el widget_id generado (auto_increment) para el Paso 5.
-- Ejemplo: widget_id = 18
```

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `widget_id` | `INT` AUTO_INCREMENT | PK |
| `widget_name` | `VARCHAR(100)` | **DEBE coincidir EXACTAMENTE** con la clave en `WIDGET_REGISTRY` |
| `description` | `VARCHAR(255)` | Nombre legible mostrado en la UI |
| `is_active` | `TINYINT(1)` | `1` = activo, `0` = deshabilitado |

---

### 2.6 Paso 5 — Agregar a layout_config

**Tabla:** `dashboard_template` (en la BD del tenant)

El campo `layout_config` es un JSON que define qué widgets y filtros están habilitados para un template:

```sql
-- Ver la config actual:
SELECT template_id, layout_config 
FROM dashboard_template 
WHERE tenant_id = X AND role = 'ADMIN';

-- Actualizar agregando el nuevo widget_id:
UPDATE dashboard_template
SET layout_config = JSON_SET(
    layout_config,
    '$.widgets',
    JSON_ARRAY_APPEND(
        JSON_EXTRACT(layout_config, '$.widgets'),
        '$', 18  -- widget_id del nuevo widget
    )
)
WHERE template_id = Y;
```

Estructura del `layout_config`:

```json
{
    "widgets": [1, 2, 3, 4, 5, 18],
    "filters": [1, 2, 3, 4, 5]
}
```

> **IMPORTANTE:** Si el `widget_id` no está en `layout_config.widgets`, el widget NO aparecerá en el dashboard de ese template/role, aunque esté registrado en todo lo demás.

---

### 2.7 Paso 6 (CONDICIONAL) — Nuevo render_type

> **Este paso solo es necesario si introduces un `render` que NO existe en la lista de tipos existentes** (ver tabla en [2.1](#21-pipeline-completo-de-un-widget)).

Si, por ejemplo, creas un render_type `"gauge"`:

#### 6a. Crear partial HTML

**Archivo:** `new_app/templates/dashboard/partials/widgets/_widget_gauge.html`

```html
{# ── Gauge Widget partial ──
     Expects: wid from parent loop
     Data shape: { value, min, max, thresholds }
#}
<div x-show="widgetResults['{{ wid }}'] && widgetResults['{{ wid }}'].data && !(widgetResults['{{ wid }}'].metadata && widgetResults['{{ wid }}'].metadata.empty){% if w.downtime_only %} && !isMultiLine{% endif %}"
     x-cloak class="widget-card-body">
  <h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2"
      x-text="widgetResults['{{ wid }}']?.widget_name"></h3>
  
  <!-- Contenido del gauge -->
  <div class="flex items-center justify-center">
    <!-- Tu implementación aquí -->
  </div>
</div>
```

**Patrón obligatorio del `x-show`:**
```
widgetResults['{{ wid }}'] && widgetResults['{{ wid }}'].data && !(widgetResults['{{ wid }}'].metadata && widgetResults['{{ wid }}'].metadata.empty)
```
Opcionalmente agregar `&& !isMultiLine` si `downtime_only: True`.

#### 6b. Agregar branch en `_main_content.html`

**Archivo:** `new_app/templates/dashboard/partials/_main_content.html`

Agregar el `elif` ANTES del `else` final:

```html
        {# ── Widget type partials (server-time decision) ── #}
        {% if wtype in ('kpi', 'kpi_oee') %}
          {% include 'dashboard/partials/widgets/_widget_kpi.html' %}
        {% elif wtype == 'chart' %}
          {% include 'dashboard/partials/widgets/_widget_chart.html' %}
        {% elif wtype == 'table' %}
          {% include 'dashboard/partials/widgets/_widget_table.html' %}
        {% elif wtype == 'indicator' %}
          {% include 'dashboard/partials/widgets/_widget_indicator.html' %}
        {% elif wtype == 'summary' %}
          {% include 'dashboard/partials/widgets/_widget_summary.html' %}
        {% elif wtype == 'feed' %}
          {% include 'dashboard/partials/widgets/_widget_feed.html' %}
        {% elif wtype == 'gauge' %}                                          {# ← NUEVO #}
          {% include 'dashboard/partials/widgets/_widget_gauge.html' %}       {# ← NUEVO #}
        {% else %}
          {% include 'dashboard/partials/widgets/_widget_unknown.html' %}
        {% endif %}
```

---

### 2.8 Paso 7 (CONDICIONAL) — Nuevo chart_type

> **Este paso solo es necesario si introduces un `chart_type` que NO existe en la lista de tipos existentes** (ver tabla en [2.1](#21-pipeline-completo-de-un-widget)).

Si, por ejemplo, creas un chart_type `"radar_chart"`:

#### 7a. Agregar builder en chart-renderer.js

**Archivo:** `new_app/static/js/chart-renderer.js`

```javascript
const ChartRenderer = {
  // ... builders existentes ...

  buildRadarConfig(data, resetBtn) {
    return {
      type: 'radar',
      data: {
        labels: data.labels || [],
        datasets: (data.datasets || []).map(ds => ({
          label: ds.label || '',
          data: ds.data || [],
          borderColor: ds.borderColor || '#22c55e',
          backgroundColor: ds.backgroundColor || 'rgba(34,197,94,0.15)',
          pointBackgroundColor: ds.borderColor || '#22c55e',
          pointBorderColor: '#fff',
          pointRadius: 4,
        })),
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          r: {
            grid: { color: 'rgba(148,163,184,0.15)' },
            ticks: { color: '#94a3b8', backdropColor: 'transparent' },
            pointLabels: { color: '#94a3b8', font: { size: 11 } },
          },
        },
        plugins: {
          legend: { position: 'top', labels: { color: '#94a3b8' } },
          tooltip: this._tooltipDefaults(),
        },
      },
    };
  },

  // Agregar al mapa de builders:
  _configBuilders: {
    'line_chart':      'buildLineConfig',
    'bar_chart':       'buildBarConfig',
    'comparison_bar':  'buildBarConfig',
    'pie_chart':       'buildPieConfig',
    'scatter_chart':   'buildScatterConfig',
    'radar_chart':     'buildRadarConfig',     // ← NUEVO
  },

  // ...
};
```

#### 7b. Agregar mapping en CHART_TYPE_MAP

**Archivo:** `new_app/static/js/dashboard-app.js`

```javascript
const CHART_TYPE_MAP = {
    'ProductionTimeChart':      'line_chart',
    'AreaDetectionChart':       'bar_chart',
    'ProductDistributionChart': 'pie_chart',
    'EntryOutputCompareChart':  'comparison_bar',
    'ScatterChart':             'scatter_chart',
    'MiNuevoChartWidget':       'radar_chart',     // ← NUEVO
};
```

> **NOTA:** La key es el `widget_name` (nombre de clase Python), el value es el `chart_type` string que debe coincidir con `_configBuilders`.

---

## 3. Widgets por Categoría: Plantillas y Data Shapes

### 3.1 KPI

**render_type:** `"kpi"` o `"kpi_oee"`

#### Data shape — KPI simple:

```python
return self._result(
    "kpi",
    {
        "value": 1234,                # Valor principal (int | float)
        "unit": "unidades",           # Unidad de medida
        "trend": None,                # Tendencia (reservado, aún no implementado)
    },
    category="kpi",
)
```

**Frontend:** Muestra `value` en grande + `unit` pequeño.

#### Data shape — KPI con extra (ej. total_minutes para KpiTotalDowntime):

```python
return self._result(
    "kpi",
    {
        "value": 5,                   # Cantidad de paradas
        "unit": "paradas",
        "trend": None,
        "total_minutes": 45.3,        # Campo extra
    },
    category="kpi",
)
```

**Frontend:** Muestra campo extra si `downtime_only` y `wtype == 'kpi'`.

#### Data shape — KPI OEE (render_type: `"kpi_oee"`):

```python
return self._result(
    "kpi",
    {
        "value": 78.5,                # OEE %
        "unit": "%",
        "availability": 92.3,
        "performance": 87.1,
        "quality": 97.6,
        "scheduled_minutes": 480.0,
        "downtime_minutes": 36.8,
        "trend": None,
    },
    category="kpi",
)
```

**Frontend:** Grid 3 columnas (Disponibilidad/Rendimiento/Calidad) + minutos programados/paradas.

#### Ejemplo completo — KPI simple:

```python
"""KPI: Total Production — count of 'output' detections."""

from new_app.services.widgets.base import BaseWidget, WidgetResult


class KpiTotalProduction(BaseWidget):

    def process(self) -> WidgetResult:
        df = self.df
        if not df.empty and "area_type" in df.columns:
            value = int(len(df[df["area_type"] == "output"]))
        else:
            value = len(df)

        unit = self.ctx.config.get("unit", "unidades")

        return self._result(
            "kpi",
            {"value": value, "unit": unit, "trend": None},
            category="kpi",
        )
```

**Registry:**
```python
"KpiTotalProduction": {
    "category": "kpi",
    "source_type": "internal",
    "required_columns": ["area_type"],
    "api_source_id": None,
    "default_config": {"unit": "unidades"},
},
```

**Render map:**
```python
"KpiTotalProduction": {"render": "kpi", "size": "small"},
```

---

### 3.2 Chart

**render_type:** `"chart"`

#### Data shape — Gráfico genérico:

```python
return self._result(
    "chart",
    {
        "labels": ["Ene", "Feb", "Mar"],          # Etiquetas eje X
        "datasets": [                              # Uno o más datasets
            {
                "label": "Producción",
                "data": [100, 200, 150],
                "borderColor": "#22c55e",          # Color de línea/borde
                "backgroundColor": "rgba(34,197,94,0.08)",
                "fill": False,                     # Solo line_chart
            },
        ],
        "curve_type": "smooth",                    # Solo line_chart
        "class_details": {                         # Tooltip breakdown por bucket
            "01/01 08:00": {"Producto A": 30, "Producto B": 70},
        },
        "downtime_events": [                       # Overlay de downtimes (line_chart)
            {
                "xMin": 3,
                "xMax": 5,
                "start_time": "10:30",
                "end_time": "11:15",
                "duration_min": 45.0,
                "reason": "Falla mecánica",
                "has_incident": True,
                "source": "db",
                "line_name": "Línea 1",
            },
        ],
        "summary": {                               # Solo comparison_bar
            "entrada": 500,
            "salida": 480,
            "descarte": 20,
        },
    },
    category="chart",
)
```

#### Data shape — Scatter chart:

```python
return self._result(
    "chart",
    {
        "datasets": [
            {
                "label": "Paradas DB",
                "data": [
                    {"x": 8.5, "y": 15.2, "tooltip": "Línea 1 — 10:30"},
                    {"x": 14.3, "y": 5.0, "tooltip": "Línea 2 — 14:18"},
                ],
                "backgroundColor": "#ef4444",
                "borderColor": "#ef4444",
                "pointRadius": 6,
            },
        ],
    },
    category="chart",
)
```

#### Data shape — Pie/Doughnut chart:

```python
return self._result(
    "chart",
    {
        "labels": ["Producto A", "Producto B", "Producto C"],
        "datasets": [
            {
                "data": [45, 30, 25],
                "backgroundColor": ["#22c55e", "#3b82f6", "#f59e0b"],
            },
        ],
    },
    category="chart",
)
```

**Registry (ejemplo line_chart):**
```python
"ProductionTimeChart": {
    "category": "chart",
    "source_type": "internal",
    "required_columns": ["detected_at", "area_type", "line_id"],
    "api_source_id": None,
    "default_config": {"curve_type": "smooth"},
},
```

**Render map:**
```python
"ProductionTimeChart": {
    "render": "chart",
    "chart_type": "line_chart",
    "size": "large",
    "chart_height": "300px",
},
```

---

### 3.3 Table

**render_type:** `"table"`

#### Data shape:

```python
return self._result(
    "table",
    {
        "columns": [                            # Definición de columnas
            {"key": "start_time", "label": "Inicio"},
            {"key": "duration_min", "label": "Duración (min)"},
            {"key": "failure_type", "label": "Tipo de Falla"},
        ],
        "rows": [                               # Lista de filas
            {
                "start_time": "2024-01-15 08:30",
                "duration_min": 15.5,
                "failure_type": "Mecánica",
            },
            # ... más filas ...
        ],
        "total_production": 1234,               # Opcional: para barras de porcentaje
    },
    category="table",
    total_rows=42,                              # Metadata
)
```

**Frontend:** Tabla con header dark (`surface-800`), rows con hover, scroll horizontal si necesario, barras de porcentaje si `total_production` presente.

**Registry:**
```python
"DowntimeTable": {
    "category": "table",
    "source_type": "internal",
    "required_columns": [],
    "api_source_id": None,
    "default_config": {},
},
```

**Render map:**
```python
"DowntimeTable": {"render": "table", "size": "large", "downtime_only": True},
```

---

### 3.4 Indicator

**render_type:** `"indicator"`

#### Data shape:

```python
return self._result(
    "indicator",
    {
        "lines": [
            {
                "line_id": 1,
                "line_name": "Línea 1",
                "line_code": "L1",
                "status": "active",           # "active" | "idle" | "no_data"
                "detection_count": 500,
                "output_count": 480,
                "last_detection": "2024-01-15 14:30",
                "minutes_since_last": 2.5,
            },
            # ... más líneas ...
        ],
        "total_lines": 3,
    },
    category="status",
    total_lines=3,
)
```

**Frontend:** Tarjetas por línea con indicador de pulso animado (verde=active, amarillo=idle, gris=no_data).

**Registry:**
```python
"LineStatusIndicator": {
    "category": "indicator",
    "source_type": "internal",
    "required_columns": ["line_id", "line_name"],
    "api_source_id": None,
    "default_config": {},
},
```

**Render map:**
```python
"LineStatusIndicator": {"render": "indicator", "size": "medium"},
```

---

### 3.5 Summary

**render_type:** `"summary"`

#### Data shape:

```python
return self._result(
    "summary",
    {
        "total_detections": 5000,
        "output_count": 4800,
        "total_weight": 2400.50,
        "avg_per_hour": 120.5,
        "hours_span": 39.8,
        "unique_products": 12,
        "lines_count": 3,
        "downtime_count": 7,
        "downtime_minutes": 85.3,
        "first_detection": "2024-01-15 06:00",
        "last_detection": "2024-01-17 21:45",
    },
    category="summary",
)
```

**Frontend:** Grid de 8+ métricas con iconos, valores formateados y unidades.

**Registry:**
```python
"MetricsSummary": {
    "category": "summary",
    "source_type": "internal",
    "required_columns": ["detected_at", "area_type", "line_id"],
    "api_source_id": None,
    "default_config": {},
},
```

**Render map:**
```python
"MetricsSummary": {"render": "summary", "size": "full"},
```

---

### 3.6 Feed

**render_type:** `"feed"`

#### Data shape:

```python
return self._result(
    "feed",
    {
        "events": [
            {
                "type": "detection",           # "detection" | "downtime" | custom
                "timestamp": "2024-01-15 14:30:25",
                "line_name": "Línea 1",
                "area_name": "Salida",         # Solo detection
                "product_name": "Producto A",  # Solo detection
            },
            {
                "type": "downtime",
                "timestamp": "2024-01-15 14:25:00",
                "line_name": "Línea 1",
                "duration_min": 5.3,           # Solo downtime
                "source": "db",                # Solo downtime
            },
        ],
        "total": 42,
    },
    category="feed",
)
```

**Frontend:** Lista cronológica con dots coloreados por tipo.

**Registry:**
```python
"EventFeed": {
    "category": "feed",
    "source_type": "internal",
    "required_columns": [],
    "api_source_id": None,
    "default_config": {"max_items": 50},
},
```

**Render map:**
```python
"EventFeed": {"render": "feed", "size": "medium"},
```

---

## 4. Creación de Filtros

### 4.1 Pipeline completo de un filtro

```
Paso 1 ── Crear clase Python en services/filters/types/
       │       (SOLO si el filter_type es NUEVO)
       │       (Si usa un filter_type existente → no es necesario)
       │
Paso 2 ── Agregar entrada en FILTER_REGISTRY
       │
Paso 3 ── INSERT en tabla filter (BD tenant)
       │
Paso 4 ── Agregar filter_id al layout_config en dashboard_template
       │
       └── Paso 5 (CONDICIONAL) ── Si el filter_type es NUEVO:
             ├── Crear clase en services/filters/types/
             ├── Registrar en engine.py (_TYPE_TO_MODULE + _TYPE_TO_CLASS)
             ├── Agregar import en filters/types/__init__.py
             └── Crear partial HTML en templates/dashboard/partials/
```

### filter_types existentes (NO requieren nueva clase):

| `filter_type` | Clase Python | Descripción |
|---------------|-------------|-------------|
| `daterange` | `DateRangeFilter` | Selector de rango de fecha/hora |
| `dropdown` | `DropdownFilter` | Selección única (estático o dinámico) |
| `multiselect` | `MultiselectFilter` | Selección múltiple |
| `text` | `TextFilter` | Input de texto libre |
| `number` | `NumberFilter` | Input numérico |
| `toggle` | `ToggleFilter` | Switch boolean on/off |

> **CLAVE:** A diferencia de los widgets (donde cada widget = 1 clase), varios filtros pueden compartir la misma clase base. Por ejemplo, `ProductionLineFilter`, `ShiftFilter` e `IntervalFilter` todos usan `DropdownFilter` como clase.  
> **Solo necesitas crear una nueva clase si introduces un `filter_type` completamente nuevo** (ej: `"slider"`, `"color_picker"`).

---

### 4.2 Paso 1 — Crear la clase del filtro

> **SOLO necesario si el `filter_type` es NUEVO.** Si usas `dropdown`, `multiselect`, `text`, `number`, `toggle` o `daterange`, salta al [Paso 2](#43-paso-2--registrar-en-filter_registry).

Los filtros heredan de una de dos clases base:

| Base | Para | Métodos a implementar |
|------|------|----------------------|
| `OptionsFilter` | Filtros con opciones seleccionables (dropdown, multiselect) | `validate()`, `get_default()`, `_load_options()` |
| `InputFilter` | Filtros de entrada directa (text, number, daterange, toggle) | `validate()`, `get_default()` |

#### Plantilla — OptionsFilter (filtro con opciones):

```python
"""MiNuevoFiltroTipo — Descripción."""

from __future__ import annotations
from typing import Any, Dict, List, Optional

from new_app.services.filters.base import FilterConfig, FilterOption, OptionsFilter


class MiNuevoFiltroTipo(OptionsFilter):
    """Filtro personalizado con opciones."""

    def _load_options(
        self,
        parent_values: Optional[Dict[str, Any]] = None,
    ) -> List[FilterOption]:
        """Cargar opciones — de cache, API, o estáticas."""
        return [
            FilterOption(value="opt1", label="Opción 1"),
            FilterOption(value="opt2", label="Opción 2"),
        ]

    def validate(self, value: Any) -> bool:
        if value is None:
            return not self.config.required
        # Validar que el valor está en las opciones
        return any(o.value == value for o in self.get_options())

    def get_default(self) -> Any:
        return self.config.default_value

    def to_sql_clause(self, value: Any) -> Optional[tuple[str, dict]]:
        """Opcional: contribución al WHERE clause."""
        if value is None:
            return None
        col = self.config.param_name
        return f"{col} = :{col}", {col: value}
```

#### Plantilla — InputFilter (filtro de entrada):

```python
"""MiNuevoInputFilter — Descripción."""

from __future__ import annotations
from typing import Any, Optional

from new_app.services.filters.base import InputFilter


class MiNuevoInputFilter(InputFilter):
    """Filtro de entrada personalizado."""

    def validate(self, value: Any) -> bool:
        if value is None:
            return not self.config.required
        # Tu lógica de validación
        return isinstance(value, (int, float))

    def get_default(self) -> Any:
        return self.config.default_value

    def to_sql_clause(self, value: Any) -> Optional[tuple[str, dict]]:
        if value is None:
            return None
        col = self.config.param_name
        return f"{col} = :{col}", {col: value}
```

#### Registrar el nuevo tipo en el engine:

**Archivo:** `new_app/services/filters/engine.py`

```python
_TYPE_TO_MODULE: dict[str, str] = {
    "daterange":   "daterange",
    "dropdown":    "dropdown",
    "multiselect": "multiselect",
    "text":        "text",
    "number":      "number",
    "toggle":      "toggle",
    "mi_tipo":     "mi_tipo",          # ← NUEVO
}

_TYPE_TO_CLASS: dict[str, str] = {
    "daterange":   "DateRangeFilter",
    "dropdown":    "DropdownFilter",
    "multiselect": "MultiselectFilter",
    "text":        "TextFilter",
    "number":      "NumberFilter",
    "toggle":      "ToggleFilter",
    "mi_tipo":     "MiNuevoFiltroTipo",  # ← NUEVO
}
```

**Archivo:** `new_app/services/filters/types/__init__.py`

```python
from new_app.services.filters.types.mi_tipo import MiNuevoFiltroTipo

__all__ = [
    # ... existentes ...
    "MiNuevoFiltroTipo",
]
```

---

### 4.3 Paso 2 — Registrar en FILTER_REGISTRY

**Archivo:** `new_app/config/filter_registry.py`

```python
FILTER_REGISTRY: dict[str, dict] = {
    # ... filtros existentes ...

    "MiNuevoFiltro": {
        "filter_type": "dropdown",          # Un filter_type existente o nuevo
        "param_name": "mi_param",           # Nombre del parámetro HTTP
        "options_source": "production_lines", # Cache key para opciones dinámicas (o None)
        "default_value": None,              # Valor por defecto
        "placeholder": "Seleccionar...",    # Texto placeholder
        "required": False,                  # ¿Obligatorio?
        "depends_on": None,                 # param_name del filtro padre (cascade)
        "ui_config": {},                    # Config extra para el frontend
    },
}
```

#### Campos del FILTER_REGISTRY:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `filter_type` | `str` | Tipo de control: `daterange`, `dropdown`, `multiselect`, `text`, `number`, `toggle` |
| `param_name` | `str` | Nombre del query parameter en HTTP |
| `options_source` | `str\|None` | Clave del cache para opciones dinámicas: `"production_lines"`, `"shifts"`, `"areas"`, `"products"`. `None` para filtros estáticos |
| `default_value` | `Any` | Valor por defecto cuando el usuario no selecciona nada |
| `placeholder` | `str\|None` | Texto placeholder del input |
| `required` | `bool` | Si `True`, la validación falla si no hay valor |
| `depends_on` | `str\|None` | `param_name` del filtro padre para cascade. Ej: `"line_id"` hace que este filtro se recargue cuando cambia la línea |
| `ui_config` | `dict` | Configuración extra para el frontend |

#### Variantes de ui_config:

**Opciones estáticas (sin `options_source`):**
```python
"ui_config": {
    "static_options": [
        {"value": "hour", "label": "Por hora"},
        {"value": "day", "label": "Por día"},
        {"value": "week", "label": "Por semana"},
    ]
},
```

**DateRange:**
```python
"ui_config": {
    "show_time": True,
    "default_start_time": "00:00",
    "default_end_time": "23:59",
},
```

**Number:**
```python
"ui_config": {
    "min": 0,
    "step": 10,
    "unit": "s",
},
```

**Toggle:**
```python
"ui_config": {
    "label": "Mostrar paradas",
},
```

**Text:**
```python
"ui_config": {
    "debounce_ms": 300,
},
```

**Dropdown con soporte para grupos:**
```python
"ui_config": {
    "supports_groups": True,
},
```

---

### 4.4 Paso 3 — INSERT en base de datos

**Tabla:** `filter` (en la BD del tenant: `db_client_{tenant_id}`)

```sql
INSERT INTO filter (filter_name, description, display_order, is_active)
VALUES ('MiNuevoFiltro', 'Descripción del filtro', 10, 1);

-- Anotar el filter_id generado para el Paso 4.
-- Ejemplo: filter_id = 11
```

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `filter_id` | `INT` AUTO_INCREMENT | PK |
| `filter_name` | `VARCHAR(100)` | **DEBE coincidir EXACTAMENTE** con la clave en `FILTER_REGISTRY` |
| `description` | `VARCHAR(255)` | Descripción legible |
| `display_order` | `INT` | Orden de aparición en el panel (menor = primero) |
| `is_active` | `TINYINT(1)` | `1` = activo, `0` = deshabilitado |
| `additional_filter` | `JSON` | Config extra (ej: grupos de líneas) |

---

### 4.5 Paso 4 — Agregar a layout_config

```sql
UPDATE dashboard_template
SET layout_config = JSON_SET(
    layout_config,
    '$.filters',
    JSON_ARRAY_APPEND(
        JSON_EXTRACT(layout_config, '$.filters'),
        '$', 11  -- filter_id del nuevo filtro
    )
)
WHERE template_id = Y;
```

---

### 4.6 Paso 5 (CONDICIONAL) — Nuevo filter_type

> **Solo necesario si introduces un `filter_type` que NO existe** (ej: `"slider"`, `"color_picker"`, `"date_single"`).

Pasos requeridos:

1. **Crear clase** en `new_app/services/filters/types/{mi_tipo}.py` (ver [4.2](#42-paso-1--crear-la-clase-del-filtro))
2. **Registrar en engine** — agregar a `_TYPE_TO_MODULE` y `_TYPE_TO_CLASS` en `engine.py`
3. **Agregar import** en `filters/types/__init__.py`
4. **Crear partial HTML** para el panel de filtros en `templates/dashboard/partials/`

---

## 5. Filtros por Tipo: Plantillas y Ejemplos

### 5.1 DateRange

**Caso de uso:** Selector de rango de fecha con hora opcional.

```python
# FILTER_REGISTRY
"MiFechaFilter": {
    "filter_type": "daterange",
    "param_name": "mi_daterange",
    "options_source": None,
    "default_value": None,      # get_default() calcula 7 días atrás
    "placeholder": None,
    "required": True,
    "depends_on": None,
    "ui_config": {
        "show_time": True,
        "default_start_time": "06:00",
        "default_end_time": "22:00",
    },
},
```

**Valor que recibe el backend:**
```json
{
    "start_date": "2024-01-15",
    "end_date": "2024-01-22",
    "start_time": "06:00",
    "end_time": "22:00"
}
```

**SQL generado:**
```sql
detected_at BETWEEN :start_dt AND :end_dt
```

---

### 5.2 Dropdown

**Caso A: Opciones dinámicas desde cache:**
```python
"NuevaLineaFilter": {
    "filter_type": "dropdown",
    "param_name": "nueva_linea",
    "options_source": "production_lines",  # Carga de MetadataCache
    "default_value": None,
    "placeholder": "Seleccionar línea",
    "required": True,
    "depends_on": None,
    "ui_config": {"supports_groups": True},
},
```

**Caso B: Opciones estáticas:**
```python
"IntervalFilter": {
    "filter_type": "dropdown",
    "param_name": "interval",
    "options_source": None,                # Sin fuente dinámica
    "default_value": "hour",
    "placeholder": None,
    "required": True,
    "depends_on": None,
    "ui_config": {
        "static_options": [
            {"value": "hour", "label": "Por hora"},
            {"value": "day", "label": "Por día"},
        ]
    },
},
```

**options_source disponibles:**

| Valor | Fuente | Datos |
|-------|--------|-------|
| `"production_lines"` | `metadata_cache.get_production_lines()` | Líneas + grupos |
| `"shifts"` | `metadata_cache.get_shifts()` | Turnos |
| `"areas"` | `metadata_cache.get_areas()` | Áreas (soporta cascade por `line_id`) |
| `"products"` | `metadata_cache.get_products()` | Productos |

**Agregar un nuevo `options_source`:**

En `new_app/services/filters/types/dropdown.py`, agregar un loader al diccionario `_LOADERS`:

```python
def _load_custom_source(flt: DropdownFilter, parent_values) -> List[FilterOption]:
    data = metadata_cache.get_custom_data()  # Tu fuente de datos
    return [
        FilterOption(value=k, label=v["name"])
        for k, v in data.items()
    ]

_LOADERS: Dict[str, Any] = {
    "production_lines": _load_production_lines,
    "shifts": _load_shifts,
    "areas": _load_areas,
    "products": _load_products,
    "custom_source": _load_custom_source,      # ← NUEVO
}
```

---

### 5.3 Multiselect

Idéntico a dropdown pero permite selección múltiple. El valor es un `list`:

```python
"NuevoMultiFilter": {
    "filter_type": "multiselect",
    "param_name": "mis_ids",
    "options_source": "products",
    "default_value": [],                    # Lista vacía por defecto
    "placeholder": "Todos los items",
    "required": False,
    "depends_on": "line_id",               # Cascade: recarga cuando cambia line_id
    "ui_config": {},
},
```

**Valor que recibe el backend:**
```json
{"mis_ids": [1, 3, 7]}
```

---

### 5.4 Text

```python
"BuscadorFilter": {
    "filter_type": "text",
    "param_name": "buscar",
    "options_source": None,
    "default_value": "",
    "placeholder": "Buscar producto…",
    "required": False,
    "depends_on": None,
    "ui_config": {"debounce_ms": 300},
},
```

---

### 5.5 Number

```python
"LimiteFilter": {
    "filter_type": "number",
    "param_name": "limite",
    "options_source": None,
    "default_value": 100,
    "placeholder": "Cantidad",
    "required": False,
    "depends_on": None,
    "ui_config": {
        "min": 0,
        "max": 10000,
        "step": 50,
        "unit": "uds",
    },
},
```

---

### 5.6 Toggle

```python
"MostrarInactivosFilter": {
    "filter_type": "toggle",
    "param_name": "show_inactive",
    "options_source": None,
    "default_value": False,
    "placeholder": None,
    "required": False,
    "depends_on": None,
    "ui_config": {"label": "Mostrar inactivos"},
},
```

**Valor que recibe el backend:**
```json
{"show_inactive": true}
```

---

## 6. Resolución Automática (Discovery)

### Widget Discovery Pipeline

```
1. widget_catalog (BD) → widget_name = "KpiTotalProduction"
2. WIDGET_REGISTRY["KpiTotalProduction"] → metadata (category, required_columns, ...)
3. WidgetEngine._class_to_module("KpiTotalProduction") → "kpi_total_production"
4. importlib("new_app.services.widgets.types.kpi_total_production") → module
5. getattr(module, "KpiTotalProduction") → class
6. WidgetContext(data=scoped_df, downtime=dt_df, params=cleaned, ...) → ctx
7. widget.process() → WidgetResult
8. WidgetResult.to_dict() → JSON para el frontend
```

### Filter Discovery Pipeline

```
1. filter (BD) → filter_name = "ProductionLineFilter"
2. FILTER_REGISTRY["ProductionLineFilter"] → metadata (filter_type="dropdown", ...)
3. _TYPE_TO_MODULE["dropdown"] → "dropdown"
4. _TYPE_TO_CLASS["dropdown"] → "DropdownFilter"
5. importlib("new_app.services.filters.types.dropdown") → module
6. getattr(module, "DropdownFilter") → class
7. FilterConfig(merged DB + registry) → config
8. DropdownFilter(config) → instance
```

### Diferencia clave entre Widget y Filter discovery:

| Aspecto | Widget | Filter |
|---------|--------|--------|
| **1 clase = 1 instancia?** | Sí. Cada widget tiene su propia clase Python | No. Múltiples filtros comparten clase (`DropdownFilter`) |
| **Resolución del módulo** | Por nombre de clase (CamelCase→snake_case) | Por `filter_type` (mapa fijo `_TYPE_TO_MODULE`) |
| **Diferenciación** | Clase Python completa | Configuración en `FILTER_REGISTRY` |

---

## 7. Checklist Rápido

### Nuevo Widget (render_type EXISTENTE)

- [ ] Crear `new_app/services/widgets/types/{snake_case}.py` — clase que hereda `BaseWidget`, implementa `process()`
- [ ] Agregar entrada en `WIDGET_REGISTRY` (`new_app/config/widget_registry.py`)
- [ ] Agregar entrada en `WIDGET_RENDER_MAP` (`new_app/config/widget_registry.py`)
- [ ] `INSERT INTO widget_catalog` en BD tenant
- [ ] Agregar `widget_id` a `layout_config.widgets` en `dashboard_template`

### Nuevo Widget (render_type NUEVO)

- [ ] Todo lo anterior, **más:**
- [ ] Crear partial HTML en `new_app/templates/dashboard/partials/widgets/_widget_{tipo}.html`
- [ ] Agregar `{% elif wtype == '{tipo}' %}` en `_main_content.html`

### Nuevo Widget Chart (chart_type NUEVO)

- [ ] Todo lo de widget existente, **más:**
- [ ] Agregar builder `build{Tipo}Config()` en `chart-renderer.js`
- [ ] Agregar entrada en `_configBuilders` en `chart-renderer.js`
- [ ] Agregar mapping en `CHART_TYPE_MAP` en `dashboard-app.js`

### Nuevo Filtro (filter_type EXISTENTE)

- [ ] Agregar entrada en `FILTER_REGISTRY` (`new_app/config/filter_registry.py`)
- [ ] `INSERT INTO filter` en BD tenant
- [ ] Agregar `filter_id` a `layout_config.filters` en `dashboard_template`
- [ ] **(Si `options_source` nuevo):** Agregar loader en `dropdown.py` → `_LOADERS`

### Nuevo Filtro (filter_type NUEVO)

- [ ] Todo lo anterior, **más:**
- [ ] Crear clase en `new_app/services/filters/types/{mi_tipo}.py`
- [ ] Agregar a `_TYPE_TO_MODULE` y `_TYPE_TO_CLASS` en `engine.py`
- [ ] Agregar import en `filters/types/__init__.py`
- [ ] Crear partial HTML en `templates/dashboard/partials/` (si el UI lo requiere)

---

## Apéndice A — Convención de nombres

| Concepto | Convención | Ejemplo |
|----------|-----------|---------|
| Clase Python (widget) | `CamelCase` | `KpiTotalProduction` |
| Archivo Python (widget) | `snake_case` | `kpi_total_production.py` |
| widget_name (BD) | Igual que clase Python | `KpiTotalProduction` |
| render_type | `snake_case` | `kpi`, `chart`, `table` |
| chart_type | `snake_case` | `line_chart`, `bar_chart` |
| filter_name (BD) | Igual que clase Python | `DateRangeFilter` |
| param_name (filtro) | `snake_case` | `line_id`, `daterange` |
| Partial HTML | `_widget_{render_type}.html` | `_widget_kpi.html` |

## Apéndice B — Errores comunes

| Error | Causa | Solución |
|-------|-------|----------|
| `Widget not registered` | `widget_name` en BD no coincide con key en `WIDGET_REGISTRY` | Verificar que el string es idéntico (case-sensitive) |
| `Class 'X' not found` | Archivo Python no existe o nombre de clase no coincide | Verificar conversión CamelCase→snake_case del nombre de archivo |
| Widget no aparece | `widget_id` no está en `layout_config.widgets` | Agregar al JSON en `dashboard_template` |
| Chart no renderiza | `chart_type` sin builder en `chart-renderer.js` | Agregar builder + entrada en `_configBuilders` |
| Chart no se invoca | `widget_name` sin entrada en `CHART_TYPE_MAP` | Agregar mapping en `dashboard-app.js` |
| Filtro no aparece | `filter_id` no está en `layout_config.filters` | Agregar al JSON en `dashboard_template` |
| `no class for type 'X'` | `filter_type` no registrado en `_TYPE_TO_MODULE` | Registrar en `engine.py` |
| Widget se muestra en unknown | `render_type` sin branch en `_main_content.html` | Agregar `{% elif %}` para el nuevo tipo |
| Data Scoping vacío | `required_columns` no coincide con columnas del DataFrame | Verificar nombres de columnas en la query master |
