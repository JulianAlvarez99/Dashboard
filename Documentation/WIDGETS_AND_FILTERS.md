# Guía Completa: Widgets y Filtros — Camet Analytics

Cómo funciona el sistema, cómo se procesan los datos, y cómo **agregar nuevos widgets y filtros** usando el patrón auto-discovery.

**Última actualización:** 5 Marzo 2026

---

## 1. Arquitectura General: Auto-Discovery

Tanto widgets como filtros usan el **mismo patrón de auto-discovery**:

```
Nombre de clase en DB (CamelCase)
    ↓  CamelCase → snake_case (regex)
nombre_de_clase.py  (archivo en types/)
    ↓  importlib.import_module(...)
class NombreDeClase(BaseWidget / BaseFilter)
    ↓  instanciar y ejecutar
```

**Ventaja:** Para agregar un nuevo widget o filtro, solo se necesita:
1. Crear un archivo `.py` en el directorio `types/`
2. Insertar un registro en la tabla `widget_catalog` o `filter` de la DB
3. El engine lo descubre automáticamente — **sin modificar registros, fábricas, ni imports**

---

## 2. Sistema de Widgets

### 2.1 Contratos: BaseWidget, WidgetContext, WidgetResult

**`new_app/services/widgets/base.py`**

#### `WidgetContext` — Datos de entrada

```python
@dataclass
class WidgetContext:
    widget_id:    int              # ID del widget en widget_catalog
    widget_name:  str              # Nombre de clase (ej. "KpiOee")
    display_name: str              # Nombre legible del widget_catalog

    data:          Any             # DataFrame de detecciones (o payload externo)
    downtime:      pd.DataFrame    # DataFrame de paradas unificado
    lines_queried: List[int]       # IDs de líneas consultadas
    params:        Dict[str, Any]  # Parámetros de filtro (cleaned)
    config:        Dict[str, Any]  # default_config de la clase + override DB
```

#### `WidgetResult` — Datos de salida

```python
@dataclass
class WidgetResult:
    widget_id:   int
    widget_name: str   # Nombre de la CLASE Python (ej. "KpiTotalProduction")
                       # ← Usado por WidgetChartBuilders para lookup en JS
    widget_type: str   # "kpi" | "kpi_oee" | "chart" | "table" | etc.
    data:        Any   # Payload JSON para el frontend
    metadata:    Dict  # Info adicional (display_name, empty, category, etc.)

    def to_dict(self) -> Dict: ...
```

> **Importante:** `widget_name` es el **nombre de la clase Python** (`self.widget_name`),
> no el nombre legible de la DB. El nombre legible (`display_name`) va dentro de `metadata`.
> Esto permite que el frontend localice el builder en `WidgetChartBuilders[widget_name]`.

#### `BaseWidget` — Clase abstracta

```python
class BaseWidget(ABC):
    # ── Atributos de LAYOUT (definen posición en el grid) ───────
    tab:          str  = "produccion"   # "produccion" | "oee"
    col_span:     int  = 1              # 1–4 columnas del grid
    row_span:     int  = 1              # 1–2 filas
    order:        int  = 99             # Orden de aparición
    downtime_only: bool = False         # Ocultar en modo multi-línea

    # ── Atributos de RENDERIZADO ─────────────────────────────────
    required_columns: List[str] = []    # Columnas del DF que necesitas
    default_config:   Dict      = {}    # Config por defecto
    render:       str = "kpi"           # Tipo de renderizado frontend
    chart_type:   str = ""              # Solo para render="chart"
    chart_height: str = "250px"         # Altura del canvas

    # ── js_inline (solo widgets chart) ──────────────────────────
    # Bloque JavaScript que registra el builder de Chart.js
    # Se inyecta en el HTML antes de chart-renderer.js
    # El builder se registra en WidgetChartBuilders[ClassName]
    js_inline: Optional[str] = None

    # ── Método obligatorio ──────────────────────────────────────
    @abstractmethod
    def process(self) -> WidgetResult: ...

    # ── Layout helper ───────────────────────────────────────────
    def get_layout(self) -> dict:
        """Retorna los atributos de layout como dict para el template."""
        return {
            "tab":          self.tab,
            "col_span":     self.col_span,
            "row_span":     self.row_span,
            "order":        self.order,
            "downtime_only": self.downtime_only,
            "render":       self.render,
            "chart_type":   self.chart_type,
            "chart_height": self.chart_height,
        }

    # ── Propiedades útiles ──────────────────────────────────────
    @property
    def df(self) -> pd.DataFrame: ...         # self.ctx.data como DataFrame
    @property
    def downtime_df(self) -> pd.DataFrame: ...
    @property
    def has_downtime(self) -> bool: ...

    # ── Helpers para construir resultados ───────────────────────
    def _result(self, widget_type, data, **meta) -> WidgetResult: ...
    def _empty(self, widget_type) -> WidgetResult: ...
```

> **Principio:** Cada widget es autónomo — su clase define tanto la lógica de negocio
> como su posición en el grid. No existe ningún registro externo de layout.

### 2.2 Tipos de `render`

| `render` | Descripción | Template Jinja2 |
|----------|-------------|-----------------|
| `kpi` | KPI simple con valor + label | `_widget_kpi.html` |
| `kpi_oee` | KPI con 4 sub-indicadores (OEE) | `_widget_kpi_oee.html` |
| `chart` | Gráfico Chart.js (usa `chart_type`) | `_widget_chart.html` |
| `table` | Tabla de datos paginada | `_widget_table.html` |
| `indicator` | Indicador con estado (colores) | `_widget_indicator.html` |
| `summary` | Resumen de métricas múltiples | `_widget_summary.html` |
| `feed` | Lista de eventos cronológicos | `_widget_feed.html` |
| `ranking` | Lista ordenada con barras | `_widget_ranking.html` |

### 2.3 `chart_type` (cuando `render = "chart"`)

| `chart_type` | Descripción |
|--------------|-------------|
| `line_chart` | Gráfico de línea (producción en el tiempo) |
| `bar_chart` | Gráfico de barras |
| `pie_chart` | Gráfico de torta/donut |
| `comparison_bar` | Barras comparativas (entrada vs salida) |
| `scatter_chart` | Scatter plot (correlaciones) |

### 2.4 Widgets Implementados (18 total)

**Tab: OEE**

| Clase | `render` | Descripción |
|-------|----------|-------------|
| `KpiOee` | `kpi_oee` | OEE + Disponibilidad + Rendimiento + Calidad |
| `KpiAvailability` | `kpi` | Disponibilidad de la línea (%) |
| `KpiPerformance` | `kpi` | Rendimiento relativo a capacidad (%) |
| `KpiQuality` | `kpi` | Tasa de calidad entrada/salida (%) |

**Tab: Producción**

| Clase | `render` | `chart_type` | Descripción |
|-------|----------|-------------|-------------|
| `KpiTotalProduction` | `kpi` | — | Total de unidades producidas |
| `KpiTotalWeight` | `kpi` | — | Peso total producido (kg) |
| `KpiTotalDowntime` | `kpi` | — | Minutos de parada (oculto multi-línea) |
| `ProductionTimeChart` | `chart` | `line_chart` | Producción por producto a lo largo del tiempo |
| `ProductDistributionChart` | `chart` | `pie_chart` | Distribución de productos (%) |
| `EntryOutputCompareChart` | `chart` | `comparison_bar` | Entrada vs Salida por período |
| `AreaDetectionChart` | `chart` | `bar_chart` | Detecciones por área |
| `ScatterChart` | `chart` | `scatter_chart` | Scatter de producción (oculto multi-línea) |
| `ProductRanking` | `ranking` | — | Ranking de productos por volumen |
| `LineStatusIndicator` | `indicator` | — | Estado actual de la línea (activa/parada) |
| `DowntimeTable` | `table` | — | Tabla de eventos de parada (oculto multi-línea) |
| `MetricsSummary` | `summary` | — | Resumen de métricas clave |
| `EventFeed` | `feed` | — | Feed de eventos cronológicos |

### 2.5 Cómo Agregar un Widget Nuevo

#### Paso 1: Crear el archivo de la clase (con layout inline)

**`new_app/services/widgets/types/mi_nuevo_widget.py`**

```python
"""
MiNuevoWidget — Descripción breve.
"""
from __future__ import annotations

from new_app.services.widgets.base import BaseWidget, WidgetResult


class MiNuevoWidget(BaseWidget):
    # ── Layout del grid (posición y visibilidad) ──────────────────
    tab          = "produccion"  # "produccion" | "oee"
    col_span     = 1             # 1–4 columnas
    row_span     = 1             # 1–2 filas
    order        = 20            # Orden de aparición (único)
    downtime_only = False        # True → ocultar en modo multi-línea

    # ── Renderizado ───────────────────────────────────────────────
    required_columns = ["detected_at", "area_type", "product_name"]
    default_config   = {"top_n": 10}
    render           = "kpi"     # o "chart", "table", "ranking", etc.
    chart_type       = ""        # Solo si render="chart"
    chart_height     = "250px"

    def process(self) -> WidgetResult:
        df = self.df  # DataFrame ya filtrado a required_columns

        if df.empty:
            return self._empty(self.render)

        valor = len(df)
        data = {
            "value": valor,
            "label": "Mi Métrica",
            "unit": "uds",
        }
        return self._result(widget_type=self.render, data=data, category="produccion")
```

**Regla de naming:** El nombre del archivo es exactamente el `CamelCase→snake_case` del nombre de la clase:
- `MiNuevoWidget` → `mi_nuevo_widget.py`
- `KpiTotalProduction` → `kpi_total_production.py`
- `ProductionTimeChart` → `production_time_chart.py`

**Para widgets de tipo `chart`**, agregar también el atributo `js_inline` que registra el builder de Chart.js en el registry global `WidgetChartBuilders`. Esto se inyecta en el HTML antes de `chart-renderer.js`:

```python
class MiChartWidget(BaseWidget):
    tab      = "produccion"
    col_span = 2
    order    = 21
    render   = "chart"
    chart_type = "bar_chart"

    js_inline = """
(function() {
  window.WidgetChartBuilders = window.WidgetChartBuilders || {};
  window.WidgetChartBuilders['MiChartWidget'] = function(data, params, utils) {
    return {
      type: 'bar',
      data: {
        labels: data.labels || [],
        datasets: [{
          label: 'Mi Dataset',
          data: data.values || [],
          backgroundColor: utils._cssVar('--color-primary'),
        }]
      },
      options: {
        responsive: true,
        scales: { y: { beginAtZero: true } },
      }
    };
  };
})();
"""

    def process(self) -> WidgetResult: ...
```

#### Paso 2: Registrar en la tabla `widget_catalog` (DB Global)

```sql
INSERT INTO widget_catalog (widget_name, display_name, description, is_active)
VALUES ('MiNuevoWidget', 'Mi Nuevo Widget', 'Descripción del widget', 1);
```

El campo `widget_name` debe coincidir **exactamente** con el nombre de la clase Python.

#### Paso 3: Asignar al `dashboard_template` en DB

```sql
-- dashboard_template.layout_config es un JSON con los widget_ids habilitados
UPDATE dashboard_template
SET layout_config = JSON_SET(layout_config, '$.widgets', JSON_ARRAY(..., {widget_id}))
WHERE id = {template_id};
```

¡Listo! El `WidgetEngine` lo descubrirá automáticamente al ejecutar el pipeline.

**Checklist mínimo:**

| # | Archivo / DB | Acción |
|---|-------------|--------|
| 1 | `services/widgets/types/mi_nuevo_widget.py` | Crear clase con layout attrs + `process()` |
| 2 | DB Global `widget_catalog` | `INSERT` con `widget_name` |
| 3 | DB Tenant `dashboard_template` | Agregar `widget_id` al layout |

---

### 2.6 Helpers Disponibles (`services/widgets/helpers.py`)

```python
from new_app.services.widgets.helpers import (
    calculate_scheduled_minutes,  # calcula minutos programados de turnos
    get_lines_with_input_output,   # líneas con áreas input Y output
    format_time_labels,            # etiquetas de tiempo por intervalo
    get_freq,                      # intervalo → pandas freq string ("H","D","W","ME")
    alpha,                         # "color" → "color" con alpha (rgba)
    FALLBACK_PALETTE,              # lista de colores fallback
    TIME_LABEL_FORMATS,            # formatos de fecha por intervalo
    find_nearest_label_index,      # índice de etiqueta más cercana
)
```

---

## 3. Sistema de Filtros

### 3.1 Contratos: BaseFilter, FilterConfig, FilterOption

**`new_app/services/filters/base.py`**

#### `FilterOption` — Una opción seleccionable

```python
@dataclass(slots=True)
class FilterOption:
    value: Any
    label: str
    extra: Optional[Dict[str, Any]] = None  # datos adicionales (ej. alias de grupo)
```

#### `FilterConfig` — Configuración de la instancia

```python
@dataclass
class FilterConfig:
    filter_id:      int
    class_name:     str          # "DateRangeFilter", "ProductionLineFilter", etc.
    filter_type:    str          # "daterange" | "dropdown" | "multiselect" | ...
    param_name:     str          # nombre del parámetro HTTP
    display_order:  int = 0
    description:    str = ""
    placeholder:    Optional[str] = None
    default_value:  Any = None
    required:       bool = False
    options_source: Optional[str] = None   # clave en MetadataCache
    depends_on:     Optional[str] = None   # cascade: param_name del padre
    ui_config:      Dict = field(default_factory=dict)
    pydantic_type:  str = "Any"            # tipo del campo en DashboardDataRequest
    js_behavior:    Dict = ...             # {serialize, include_if, on_change}
    js_validation:  Optional[Dict] = None  # reglas de validación browser (ver §3.4)
```

#### `BaseFilter` — Clase abstracta

```python
class BaseFilter(ABC):
    # ── Atributos de clase que DEBES sobreescribir ──────────────
    filter_type    : str  = ""          # "daterange" | "dropdown" | ...
    param_name     : str  = ""          # nombre del param HTTP
    options_source : Optional[str] = None
    default_value  : Any  = None
    placeholder    : Optional[str] = None
    required       : bool = False
    depends_on     : Optional[str] = None
    ui_config      : Dict = {}

    # ── Contrato frontend (auto-propagados, no editar otros archivos) ──
    pydantic_type : str            = "Any"   # tipo campo en DashboardDataRequest
    js_behavior   : Dict[str,str]  = {...}   # serialize / include_if / on_change
    js_inline     : Optional[str]  = None    # JS inyectado en el HTML (on_change, etc.)
    js_validation : Optional[Dict] = None    # reglas de validación browser

    # ── Métodos obligatorios ────────────────────────────────────
    @abstractmethod
    def validate(self, value: Any) -> bool: ...

    @abstractmethod
    def get_default(self) -> Any: ...

    # ── Métodos opcionales ──────────────────────────────────────
    def get_options(self, parent_values=None) -> List[FilterOption]: ...
    def to_sql_clause(self, value) -> Optional[tuple[str, dict]]: ...
    def to_dict(self, parent_values=None) -> Dict: ...
```

### 3.2 Tipos Base Disponibles

| Clase Base | Cuándo usar |
|------------|-------------|
| `DropdownFilter` | Selección única desde una lista |
| `MultiselectFilter` | Selección múltiple |
| `InputFilter` | Entrada de texto / número |
| `ToggleFilter` | Booleano (sí/no) |

### 3.3 Filtros Implementados (16 total)

| Clase | `filter_type` | `param_name` | `options_source` | Descripción |
|-------|---------------|-------------|------------------|-------------|
| `DateRangeFilter` | `daterange` | `daterange` | — | Rango de fechas + horas |
| `ProductionLineFilter` | `dropdown` | `line_id` | `production_lines` | Línea de producción con grupos |
| `ShiftFilter` | `dropdown` | `shift_id` | `shifts` | Turno de producción |
| `ProductFilter` | `multiselect`| `product_ids` | `products` | Productos (multi) |
| `AreaFilter` | `multiselect`| `area_ids` | `areas` | Áreas (multi) |
| `IntervalFilter` | `dropdown` | `interval` | — | Agrupación: hora/día/semana/mes |
| `CurveTypeFilter` | `dropdown` | `curve_type` | — | Tipo de curva: smooth/linear/step |
| `DowntimeThresholdFilter` | `number` | `downtime_threshold` | — | Umbral de parada (segundos) |
| `ShowDowntimeFilter` | `toggle` | `show_downtime` | — | Mostrar overlay de paradas |
| `SearchFilter` | `text` | `search` | — | Búsqueda por texto libre |
| `DropdownFilter` *(base)* | `dropdown` | — | configurable | Base para dropdowns custom |
| `MultiselectFilter` *(base)* | `multiselect` | — | configurable | Base para multiselects custom |

### 3.4 Cómo Agregar un Filtro Nuevo

#### Paso 1: Crear el archivo de la clase

**`new_app/services/filters/types/mi_filtro.py`**

```python
"""MiFiltro — Descripción breve."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from new_app.core.cache import metadata_cache
from new_app.services.filters.base import FilterConfig, FilterOption, OptionsFilter


class MiFiltro(OptionsFilter):
    """Dropdown de ejemplo que carga opciones desde la cache."""

    # ── Class attributes (auto-discovery) ──────────────────────
    filter_type    = "dropdown"        # tipo de UI a renderizar
    param_name     = "mi_param"        # nombre del parámetro HTTP
    options_source = "mi_fuente"       # clave en MetadataCache (si aplica)
    default_value  = None
    placeholder    = "Seleccionar..."
    required       = False
    depends_on     = None              # o "line_id" para cascade
    ui_config      = {}

    # ── Contrato frontend ───────────────────────────────────────
    pydantic_type = "Any"              # auto-genera campo en DashboardDataRequest
    js_behavior   = {"serialize": "raw", "include_if": "truthy", "on_change": ""}
    js_inline     = None
    js_validation = None              # ej. {"required": True} / {"enum": ["a","b"]}

    def validate(self, value: Any) -> bool:
        """True si el valor es válido."""
        return value is None or isinstance(value, int)

    def get_default(self) -> Any:
        return self.default_value

    def _load_options(
        self,
        parent_values: Optional[Dict[str, Any]] = None,
    ) -> List[FilterOption]:
        """Cargar opciones desde la cache o lógica custom."""
        # Ejemplo: cargar productos desde cache
        items = metadata_cache.get_products()  # dict[int, dict]
        return [
            FilterOption(value=k, label=v["product_name"])
            for k, v in items.items()
        ]
```

**Para filtros de entrada (sin opciones)**, hereda de `InputFilter`:

```python
from new_app.services.filters.base import FilterConfig, InputFilter


class MiFiltroNumerico(InputFilter):
    filter_type   = "number"
    param_name    = "mi_numero"
    default_value = 30
    required      = False

    # ── Contrato frontend ─────────────────────────────────────
    pydantic_type = "int"
    js_behavior   = {"serialize": "int", "include_if": "not_null", "on_change": ""}
    js_inline     = None
    js_validation = {"min": 0, "min_msg": "Debe ser un número positivo"}

    def validate(self, value: Any) -> bool:
        return value is None or (isinstance(value, int) and value > 0)

    def get_default(self) -> Any:
        return self.default_value
```

#### Paso 2: Registrar en la tabla `filter` (DB Tenant)

```sql
INSERT INTO filter (filter_name, additional_filter, is_active)
VALUES ('MiFiltro', NULL, 1);
-- filter_name debe coincidir EXACTAMENTE con el nombre de la clase Python
```

Para filtros con configuración extra (ej. grupos de líneas):
```sql
INSERT INTO filter (filter_name, additional_filter, is_active)
VALUES ('ProductionLineFilter', '{"groups": [{"alias": "Zona A", "line_ids": [1,2,3]}]}', 1);
```

#### Paso 3: Asignar al layout en `dashboard_template`

El `layout_config.filters` del template debe incluir el `filter_id` del nuevo filtro.

> **⚡ No editar `dynamic_request.py`, `request_helpers.py` ni `_buildRequestBody`/`_validateParamsLocally` en JS.**
> El modelo Pydantic, el mapping de parámetros y la serialización/validación frontend
> se auto-configuran a partir de `pydantic_type`, `js_behavior` y `js_validation`
> declarados en la clase. Ver §3.1 para detalle de cada atributo.

#### Paso 4: Implementar `to_sql_clause()` en la clase

Si la clase base no genera la cláusula SQL automáticamente, agregarla explícitamente:

```python
class MiFiltro(OptionsFilter):
    # ...

    def to_sql_clause(self, value):
        if not value:
            return None, {}
        return "mi_columna = :mi_param", {"mi_param": value}
```

Sin este paso, el valor llega al `FilterEngine` pero **no genera ninguna condición SQL**.

---

> ⚠️ **Trampa frecuente:** El auto-discovery hace que el filtro **aparezca en la UI** con solo crear el archivo `.py` y registrarlo en la DB. Esto lleva a pensar que está funcionando, cuando en realidad el Paso 4 (`to_sql_clause`) es el que conecta la selección del usuario con la query. Un filtro sin `to_sql_clause` es **decorativo**.
>
> El flujo completo de un parámetro es:
> ```
> filterStates['mi_param'].value
>     → _buildRequestBody(): serializa según js_behavior          [auto]
>     → DashboardDataRequest.mi_param (campo auto-generado)       [auto]
>     → build_filter_dict() → cleaned['mi_param']                [auto]
>     → FilterEngine
>     → to_sql_clause() → WHERE mi_columna = :mi_param           [Paso 4]
> ```
> Los eslabones marcados `[auto]` se configuran declarando `pydantic_type` y
> `js_behavior` en la clase — ningún otro archivo necesita editarse.

¡Listo! El `FilterEngine` lo descubrirá automáticamente.

---

### 3.5 `FilterEngine` — Cómo funciona

**`new_app/services/filters/engine.py`**

```python
# Obtener todos los filtros activos
all_filters = filter_engine.get_all()

# Solo filtros del layout actual (whitelist de IDs)
layout_filters = filter_engine.get_all(filter_ids=[1, 2, 5])

# Con cascade: pasar valores del filtro padre
child_opts = filter_engine.get_all(parent_values={"line_id": 3})

# Validar y normalizar parámetros del frontend
cleaned = filter_engine.validate_input(user_params)

# Serializar para el frontend
filter_list = filter_engine.resolve_all()
# → [{"filter_id": 1, "filter_type": "daterange", "options": [], ...}, ...]
```

---

## 4. Flujo Completo de un Widget

```
1. Usuario aplica filtros en el frontend
   → POST /api/v1/dashboard/data { line_id: 1, daterange: {...}, ... }

2. DashboardOrchestrator.execute(session, user_params, tenant_id, role)
   │
   ├─ FilterEngine.validate_input(user_params)
   │   → cleaned = {"line_id": 1, "start": "...", "end": "...", ...}
   │
   ├─ LineResolver.resolve(cleaned)
   │   → line_ids = [1]
   │
   ├─ WidgetResolver.resolve(tenant_id, role)
   │   → widget_names = ["KpiTotalProduction", "ProductionTimeChart", ...]
   │
   ├─ DetectionService.fetch(session, line_ids, cleaned)
   │   → master_df (enriquecido con product_name, area_type, etc.)
   │
   ├─ DowntimeService.fetch(session, line_ids, cleaned)
   │   → downtime_df (DB + gap analysis + dedup)
   │
   ├─ DashboardContext(detections, downtime, cleaned, line_ids, widget_names, catalog)
   │
   ├─ DataBroker.resolve(widget_names, master_df)
   │   Para "KpiTotalProduction" (internal):
   │   → slice df a required_columns = ["area_type"]
   │   Para "ExternalWidget" (external):
   │   → ExternalAPIService.call(api_source_id) (async)
   │
   ├─ WidgetEngine.process_widgets(names, payloads)
   │   Para "KpiTotalProduction":
   │   → import kpi_total_production → class KpiTotalProduction
   │   → ctx = WidgetContext(data=sliced_df, downtime=downtime_df, ...)
   │   → widget = KpiTotalProduction(ctx)
   │   → result = widget.process() → WidgetResult
   │
   └─ ResponseAssembler.assemble(ctx, results, elapsed)
       → {
           "widgets": {
             "1": {
               "widget_id": 1,
               "widget_name": "KpiTotalProduction",   ← nombre de clase Python
               "widget_type": "kpi",
               "data": {"value": 1250, "unit": "uds", "label": "Total"},
               "metadata": {
                 "display_name": "Total Producción",  ← nombre legible de la DB
                 "category": "produccion"
               }
             },
             ...
           },
           "metadata": {
             "total_detections": 1250,
             "lines_queried": [1],
             "is_multi_line": false,
             "elapsed_seconds": 0.35
           }
         }

3. Frontend renderiza cada widget con su partial Jinja2
   según widget_type → template _widget_{type}.html
```

---

## 5. Response Schema Completo

```json
{
  "widgets": {
    "<widget_id>": {
      "widget_id": 1,
      "widget_name": "KpiTotalProduction",
      "widget_type": "kpi",
      "data": { ... },
      "metadata": {
        "empty": false,
        "category": "produccion",
        "display_name": "Total Producción"
      }
    }
  },
  "metadata": {
    "total_detections": 1250,
    "total_downtime_events": 3,
    "lines_queried": [1],
    "is_multi_line": false,
    "widget_count": 8,
    "period": { "start": "2026-02-20", "end": "2026-02-25" },
    "interval": "hour",
    "elapsed_seconds": 0.35,
    "timestamp": "2026-02-25T10:30:00"
  },
  "raw_data": [...],        // Solo si include_raw=True
  "raw_downtime": [...]     // Solo si include_raw=True
}
```

---

## 6. Widget Data Schemas por `render` type

### `kpi`
```json
{
  "value": 1250,
  "unit": "uds",
  "label": "Total Producción",
  "trend": null
}
```

### `kpi_oee`
```json
{
  "oee": 72.3,
  "availability": 85.1,
  "performance": 91.4,
  "quality": 93.0,
  "scheduled_minutes": 480,
  "total_downtime_minutes": 71.5
}
```

### `chart` (line_chart)
```json
{
  "labels": ["08:00", "09:00", "10:00"],
  "datasets": [
    {
      "label": "Producto A",
      "data": [120, 135, 98],
      "borderColor": "#3b82f6"
    }
  ],
  "curve_type": "smooth",
  "class_details": {...},
  "downtime_events": [...]
}
```

### `table`
```json
{
  "columns": ["Inicio", "Fin", "Duración", "Tipo"],
  "rows": [
    ["10:30", "10:45", "15 min", "Micro-parada"]
  ]
}
```

### `ranking`
```json
{
  "items": [
    { "label": "Producto A", "value": 450, "percentage": 36.0 },
    { "label": "Producto B", "value": 380, "percentage": 30.4 }
  ]
}
```

---

## 7. Layout Visual (atributos de clase en cada widget)

El layout está **colocado directamente en la clase del widget**,
nunca en un dict externo. Cada widget es completamente autónomo:

```python
class KpiOee(BaseWidget):
    tab          = "oee"      # "produccion" | "oee"
    col_span     = 1          # 1-4 (grid de 4 columnas)
    row_span     = 1          # 1-2 (opcional, default 1)
    order        = 0          # orden en el grid (único por tab)
    downtime_only = False     # True → ocultar cuando is_multi_line=True
    render       = "kpi_oee"
    ...
```

`new_app/config/widget_layout.py` ahora solo exporta dos constantes:

```python
GRID_COLUMNS: int = 4        # columnas del CSS grid (usado en template)
SHOW_OEE_TAB: bool = False   # mostrar/ocultar la pestaña OEE (env flag)
```

**`downtime_only = True`** → el widget se oculta automáticamente cuando el usuario consulta múltiples líneas simultáneamente (`is_multi_line = True`). Útil para widgets que solo tienen sentido para una línea concreta (scatter, tabla de paradas, etc.).

### Sistema de gráficos Chart.js (WidgetChartBuilders)

Cada widget de tipo `chart` registra su propio builder en el registry global JavaScript `WidgetChartBuilders` mediante el atributo `js_inline`. El template inyecta todos estos bloques antes de cargar `chart-renderer.js`:

```html
<!-- Injected by routes/dashboard.py -->
<script>
  window.WidgetChartBuilders = {};
  // ProductionTimeChart.js_inline
  // ProductDistributionChart.js_inline
  // ...
</script>
<script src="chart-renderer.js"></script>
```

`chart-renderer.js` llama a `WidgetChartBuilders[widgetName](data, params, utils)` para construir la configuración de Chart.js. `utils` expone helpers de `chart-config.js` (`_cssVar`, `_curveProps`, `buildDowntimeAnnotations`, etc.).

**`chart-config.js`** — Solo utilidades compartidas (no builders de chart type específicos):
- `_cssVar(name)` — lee variables CSS del tema
- `_curveProps(curve_type)` — opciones de curva smooth/linear/step
- `_zoomOptions(enabled)` — configuración zoom/pan
- `buildDowntimeAnnotations(events)` — anotaciones de paradas
- `_tooltipDefaults()` — config de tooltip por defecto

---

## 8. DataBroker: Fuentes Internas vs Externas

El `DataBroker` clasifica cada widget por `source_type`:

```python
# ── Fuente interna (por defecto) ─────────────────────────────
# El widget recibe un slice del master DataFrame
# Los required_columns se usan para el Data Scoping

class KpiTotalProduction(BaseWidget):
    required_columns = ["area_type"]   # solo recibe esta columna
    # source_type = "internal"          ← default

# ── Fuente externa ───────────────────────────────────────────
# Configurado en widget_catalog.source_type = "external"
# y widget_catalog.api_source_id = id en external_apis.yml

# external_apis.yml:
# my_external_api:
#   base_url: "https://api.ejemplo.com"
#   endpoint: "/datos"
#   method: "GET"
#   headers: {...}
```

Para agregar un widget que consume una API externa:
1. Añadir la configuración en `new_app/config/external_apis.yml`
2. Crear la clase widget (puede recibir el payload como `ctx.data` dict)
3. En `widget_catalog`: `source_type = "external"`, `api_source_id = <key_yml>`

---

_Guía actualizada al estado real del código. Ver [ARCHITECTURE_DIAGRAMS.md](ARCHITECTURE_DIAGRAMS.md) para diagramas._
