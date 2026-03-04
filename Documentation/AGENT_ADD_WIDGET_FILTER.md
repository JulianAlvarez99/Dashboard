# Guía de Agente — Cómo Agregar un Filtro o un Widget

> **Propósito:** Este documento está escrito para ser consumido por un agente de IA.
> El usuario indica qué quiere agregar y el agente ejecuta exactamente los pasos
> detallados aquí, en orden, sin omitir ninguno.

---

## INFORMACIÓN QUE DEBES RECOPILAR ANTES DE EMPEZAR

### Para un Filtro

| Dato | Ejemplo | Descripción |
|------|---------|-------------|
| `NombreClase` | `PriorityFilter` | CamelCase, nombre único |
| `param_name` | `priority` | Snake_case, nombre del param HTTP |
| `filter_type` | `dropdown` | `dropdown` \| `multiselect` \| `number` \| `text` \| `toggle` |
| `clase_base` | `DropdownFilter` | Ver tabla de bases más abajo |
| `required` | `False` | ¿Obligatorio para ejecutar la query? |
| `default_value` | `None` | Valor por defecto si no se selecciona |
| `placeholder` | `"Todas las prioridades"` | Texto del placeholder en la UI |
| `options_source` | `None` | Clave en MetadataCache, o `None` si es estático |
| `static_options` | `[{"value": "high", "label": "Alta"}, ...]` | Solo si `options_source = None` |
| `depends_on` | `None` | `param_name` del filtro padre (cascade), o `None` |
| `tipo_sql` | `"priority = :priority"` | Cláusula SQL que genera |
| `tipo_python` | `Optional[str]` | Tipo del campo en Pydantic |

**Clases base disponibles:**

| `filter_type` | Clase base |
|---|---|
| `dropdown` | `DropdownFilter` (from `new_app.services.filters.types.dropdown`) |
| `multiselect` | `MultiselectFilter` (from `new_app.services.filters.types.multiselect`) |
| `number` | `InputFilter` (from `new_app.services.filters.base`) |
| `text` | `InputFilter` (from `new_app.services.filters.base`) |
| `toggle` | `ToggleFilter` (from `new_app.services.filters.types.toggle`) |

---

### Para un Widget

| Dato | Ejemplo | Descripción |
|------|---------|-------------|
| `NombreClase` | `KpiRejectedRate` | CamelCase, nombre único |
| `render` | `kpi` | Tipo de renderizado — ver tabla más abajo |
| `chart_type` | `""` | Solo si `render = "chart"` |
| `chart_height` | `"250px"` | Altura del canvas |
| `tab` | `"produccion"` | `"produccion"` \| `"oee"` |
| `col_span` | `1` | 1–4 columnas del grid |
| `row_span` | `1` | 1–2 filas (opcional) |
| `order` | `18` | Orden en el grid (ver los existentes en widget_layout.py) |
| `required_columns` | `["area_type", "detected_at"]` | Columnas del DataFrame que necesita |
| `downtime_only` | `False` | `True` para ocultar en modo multi-línea |
| `display_name` | `"Tasa de Rechazo"` | Texto legible para la DB |
| `description` | `"Porcentaje de unidades rechazadas"` | Descripción en widget_catalog |

**Tipos de `render` disponibles:**

| `render` | Template | Cuándo usar |
|---|---|---|
| `kpi` | `_widget_kpi.html` | Valor único con label |
| `kpi_oee` | `_widget_kpi_oee.html` | OEE con 4 sub-indicadores |
| `chart` | `_widget_chart.html` | Gráfico Chart.js (requiere `chart_type`) |
| `table` | `_widget_table.html` | Tabla paginada |
| `indicator` | `_widget_indicator.html` | Estado con colores |
| `summary` | `_widget_summary.html` | Resumen de métricas múltiples |
| `feed` | `_widget_feed.html` | Lista cronológica de eventos |
| `ranking` | `_widget_ranking.html` | Lista ordenada con barras |

---

---

## PLAN: AGREGAR UN FILTRO NUEVO

### Paso 1 — Crear la clase del filtro

**Archivo:** `new_app/services/filters/types/{nombre_clase_snake}.py`

> La regla de naming es estricta: `NombreClase` → `nombre_clase.py`
> Ejemplos: `PriorityFilter` → `priority_filter.py`, `ShiftFilter` → `shift_filter.py`

**Plantilla para filtro con opciones estáticas (sin DB):**

```python
"""{NombreClase} — {descripción breve}."""
from __future__ import annotations

from new_app.services.filters.types.dropdown import DropdownFilter


class {NombreClase}(DropdownFilter):
    """{Docstring}"""

    filter_type    = "{filter_type}"
    param_name     = "{param_name}"
    options_source = None
    default_value  = {default_value}
    placeholder    = "{placeholder}"
    required       = {required}
    depends_on     = None
    ui_config      = {
        "static_options": [
            {"value": "val1", "label": "Etiqueta 1"},
            {"value": "val2", "label": "Etiqueta 2"},
        ]
    }

    def to_sql_clause(self, value):
        if not value:
            return None, {}
        return "{columna_sql} = :{param_name}", {"{param_name}": value}
```

**Plantilla para filtro que carga opciones desde MetadataCache:**

```python
"""{NombreClase} — {descripción breve}."""
from __future__ import annotations
from typing import Any, Dict, List, Optional

from new_app.core.cache import metadata_cache
from new_app.services.filters.base import FilterOption
from new_app.services.filters.types.dropdown import DropdownFilter


class {NombreClase}(DropdownFilter):
    """{Docstring}"""

    filter_type    = "dropdown"
    param_name     = "{param_name}"
    options_source = "{options_source}"   # clave en MetadataCache
    default_value  = None
    placeholder    = "{placeholder}"
    required       = False
    depends_on     = None   # o "line_id" para cascade
    ui_config      = {}

    def _load_options(
        self,
        parent_values: Optional[Dict[str, Any]] = None,
    ) -> List[FilterOption]:
        items = metadata_cache.get_{options_source}()  # ajustar al método real
        return [
            FilterOption(value=k, label=v["nombre_campo"])
            for k, v in items.items()
        ]

    def to_sql_clause(self, value):
        if not value:
            return None, {}
        return "{columna_sql} = :{param_name}", {"{param_name}": value}
```

---

### Paso 2 — Registrar en la tabla `filter` (DB Tenant)

Ejecutar en la DB del tenant correspondiente:

```sql
INSERT INTO filter (filter_name, additional_filter, is_active)
VALUES ('{NombreClase}', NULL, 1);
```

> `filter_name` debe coincidir **exactamente** con el nombre de la clase Python.
> Anotar el `filter_id` generado — se necesita en el Paso 7.

---

### Paso 3 — Agregar el campo al modelo Pydantic

**Archivo:** `new_app/api/v1/dashboard.py`

Agregar dentro de la clase `DashboardDataRequest`, junto a los demás filter params:

```python
class DashboardDataRequest(BaseModel):
    # ...campos existentes...
    {param_name}: Optional[{tipo_python}] = None
```

> **Por qué:** Sin este campo, Pydantic descarta silenciosamente el valor
> antes de que llegue al endpoint. El frontend puede enviarlo, pero el backend
> nunca lo ve.

---

### Paso 4 — Agregar el campo al mapping de `build_filter_dict()`

**Archivo:** `new_app/utils/request_helpers.py`

Dentro de la función `build_filter_dict`, agregar al dict `mapping`:

```python
mapping = {
    # ...campos existentes...
    "{param_name}": "{param_name}",
}
```

> **Por qué:** Sin este mapping, el valor llega al endpoint pero nunca
> entra al `FilterEngine` ni llega a las queries SQL.

---

### Paso 5 — Incluir el parámetro en `_buildRequestBody()` del frontend

**Archivo:** `new_app/static/js/dashboard-orchestrator.js`

Dentro del método `_buildRequestBody(ctx)`, agregar el param al body que se envía:

```javascript
// Para un dropdown simple (string o int):
if (ctx.params.{param_name})
    body.{param_name} = ctx.params.{param_name};

// Para un multiselect (array):
if (ctx.params.{param_name} && ctx.params.{param_name}.length > 0)
    body.{param_name} = ctx.params.{param_name};

// Para un número:
if (ctx.params.{param_name} != null)
    body.{param_name} = parseInt(ctx.params.{param_name});

// Para un booleano (toggle):
if (ctx.params.{param_name})
    body.{param_name} = true;
```

> **Por qué:** Sin esto, el valor nunca sale del frontend — el body HTTP
> va sin ese campo.

---

### Paso 6 — Agregar validación local en `_validateParamsLocally()` (si aplica)

**Archivo:** `new_app/static/js/dashboard-orchestrator.js`

Solo si el filtro tiene reglas de validación en el browser (ej. valores válidos,
formato, rango). Agregar una nueva "Regla" dentro del método `_validateParamsLocally`:

```javascript
// Regla N: {nombre_param} debe ser uno de los valores válidos
const valid{Nombre} = ['val1', 'val2', 'val3'];
if (params.{param_name} && !valid{Nombre}.includes(params.{param_name})) {
    errors['{param_name}'] = `Valor inválido: ${params.{param_name}}`;
}
```

> Omitir este paso para filtros opcionales sin restricciones de formato.

---

### Paso 7 — Asignar el filtro al `dashboard_template` en DB

El template del dashboard tiene un `layout_config` JSON que define qué filtros
están activos. Agregar el `filter_id` (obtenido en el Paso 2) al array `filters`:

```sql
-- Ver el layout_config actual:
SELECT layout_config FROM dashboard_template WHERE id = {template_id};

-- Actualizar (ajustar el JSON según el formato existente):
UPDATE dashboard_template
SET layout_config = JSON_SET(layout_config, '$.filters', JSON_ARRAY(..., {filter_id}))
WHERE id = {template_id};
```

---

### ✅ Checklist de Filtro

| # | Archivo | Acción | Crítico |
|---|---------|--------|---------|
| 1 | `services/filters/types/{nombre}.py` | Crear clase con `param_name`, `to_sql_clause` | ✅ |
| 2 | DB `filter` | `INSERT` con `filter_name` | ✅ |
| 3 | `api/v1/dashboard.py` → `DashboardDataRequest` | Agregar campo Pydantic | ✅ |
| 4 | `utils/request_helpers.py` → `build_filter_dict` | Agregar al mapping | ✅ |
| 5 | `static/js/dashboard-orchestrator.js` → `_buildRequestBody` | Incluir en body HTTP | ✅ |
| 6 | `static/js/dashboard-orchestrator.js` → `_validateParamsLocally` | Validación local (si aplica) | ⚠️ |
| 7 | DB `dashboard_template` | Agregar `filter_id` al layout | ✅ |

---

---

## PLAN: AGREGAR UN WIDGET NUEVO

### Paso 1 — Crear la clase del widget

**Archivo:** `new_app/services/widgets/types/{nombre_clase_snake}.py`

> La regla de naming es estricta: `NombreClase` → `nombre_clase.py`
> Ejemplos: `KpiRejectedRate` → `kpi_rejected_rate.py`

**Plantilla:**

```python
"""
{NombreClase} — {descripción breve}.
"""
from __future__ import annotations

from new_app.services.widgets.base import BaseWidget, WidgetResult


class {NombreClase}(BaseWidget):

    # Columnas del DataFrame maestro que este widget necesita
    # (Data Scoping — solo se pasan estas columnas al widget)
    required_columns = ["{col1}", "{col2}"]

    # Config por defecto (accesible via self.ctx.config)
    default_config = {}

    # Tipo de renderizado en el frontend
    render     = "{render}"      # "kpi" | "chart" | "table" | "ranking" | etc.
    chart_type = "{chart_type}"  # solo si render = "chart"
    chart_height = "{chart_height}"

    def process(self) -> WidgetResult:
        df = self.df  # DataFrame ya filtrado a required_columns

        if df.empty:
            return self._empty(self.render)

        # --- lógica de negocio ---
        valor = len(df)

        data = {
            "value":  valor,
            "label":  "{label}",
            "unit":   "{unit}",
            "trend":  None,
        }

        return self._result(
            widget_type=self.render,
            data=data,
            category="{categoria}",  # "produccion" | "oee" | etc.
        )
```

**Helpers disponibles** (importar desde `new_app.services.widgets.helpers`):

```python
from new_app.services.widgets.helpers import (
    calculate_scheduled_minutes,
    get_lines_with_input_output,
    format_time_labels,
    get_freq,           # "hour" → "H", "day" → "D", etc.
    alpha,
    FALLBACK_PALETTE,
)
```

---

### Paso 2 — Registrar en la tabla `widget_catalog` (DB Global)

```sql
INSERT INTO widget_catalog (widget_name, display_name, description, is_active)
VALUES ('{NombreClase}', '{display_name}', '{description}', 1);
```

> `widget_name` debe coincidir **exactamente** con el nombre de la clase Python.
> Anotar el `widget_id` generado — se necesita en el Paso 4.

---

### Paso 3 — Agregar al layout de widgets

**Archivo:** `new_app/config/widget_layout.py`

Agregar una entrada al dict `WIDGET_LAYOUT`. Ver los `order` existentes para
asignar el siguiente disponible:

```python
WIDGET_LAYOUT: dict[str, dict] = {
    # ...widgets existentes...

    "{NombreClase}": {
        "tab":          "{tab}",          # "produccion" | "oee"
        "col_span":     {col_span},       # 1–4
        "row_span":     {row_span},       # 1–2 (omitir si es 1)
        "order":        {order},          # siguiente disponible
        "render":       "{render}",
        "chart_type":   "{chart_type}",   # "" si no es chart
        "chart_height": "{chart_height}",
        # "downtime_only": True,          # descomentar si ocultar en multi-línea
    },
}
```

---

### Paso 4 — Asignar al `dashboard_template` en DB (DB Tenant)

El template del dashboard tiene un `layout_config` JSON con los `widget_ids`
habilitados para cada tenant/rol. Agregar el `widget_id` del Paso 2:

```sql
-- Ver el layout_config actual:
SELECT layout_config FROM dashboard_template WHERE id = {template_id};

-- Agregar el widget_id al array correspondiente:
UPDATE dashboard_template
SET layout_config = JSON_SET(layout_config, '$.widgets', JSON_ARRAY(..., {widget_id}))
WHERE id = {template_id};
```

---

### ✅ Checklist de Widget

| # | Archivo | Acción | Crítico |
|---|---------|--------|---------|
| 1 | `services/widgets/types/{nombre}.py` | Crear clase con `process()` | ✅ |
| 2 | DB Global `widget_catalog` | `INSERT` con `widget_name` | ✅ |
| 3 | `config/widget_layout.py` → `WIDGET_LAYOUT` | Agregar entrada con tab/col_span/order | ✅ |
| 4 | DB Tenant `dashboard_template` | Agregar `widget_id` al layout | ✅ |

---

---

## REGLAS DE NAMING (resumen rápido)

```
NombreClase   →  nombre_clase.py   (archivo)
NombreClase   →  nombre_clase      (clave en DB widget_name / filter_name)
param_name    →  ctx.params.{param_name}  (Alpine.js)
param_name    →  body.{param_name}        (HTTP body)
param_name    →  req.{param_name}         (Pydantic)
param_name    →  cleaned["{param_name}"]  (FilterEngine)
```

---

## FLUJO DE DATOS (recordatorio)

### Filtro

```
Usuario selecciona valor en UI
    → Alpine: ctx.params.{param_name} = valor
    → _buildRequestBody(): body.{param_name} = valor       [Paso 5]
    → HTTP POST body
    → DashboardDataRequest.{param_name}                    [Paso 3]
    → build_filter_dict() → cleaned["{param_name}"]        [Paso 4]
    → FilterEngine.validate_input() → cleaned
    → {NombreClase}.to_sql_clause(valor)                   [Paso 1]
    → WHERE {columna} = :{param_name}
```

### Widget

```
Pipeline ejecuta
    → WidgetEngine descubre {nombre_clase}.py              [Paso 1]
    → DataBroker slicee df a required_columns
    → {NombreClase}(ctx).process() → WidgetResult
    → ResponseAssembler incluye widget_id                  [Paso 4]
    → Frontend renderiza con template _widget_{render}.html
```
