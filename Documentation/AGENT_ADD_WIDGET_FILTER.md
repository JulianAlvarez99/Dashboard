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
| `pydantic_type` | `"str"` | Tipo Pydantic del campo (`"str"` \| `"int"` \| `"bool"` \| `"Any"` \| `"List[int]"`) — declarado en la clase |
| `js_validation` | `None` | Reglas de validación browser. Ver tabla más abajo. `None` para filtros sin restricciones. |

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
| `order` | `18` | Orden en el grid (ver los existentes en cada widget) |
| `downtime_only` | `False` | `True` para ocultar en modo multi-línea |
| `required_columns` | `["area_type", "detected_at"]` | Columnas del DataFrame que necesita |
| `js_inline` | `None` | Bloque JS del builder Chart.js (solo si `render="chart"`) |
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

from typing import Any, Dict, List, Optional

from new_app.services.filters.base import FilterOption, OptionsFilter


class {NombreClase}(OptionsFilter):
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

    # ── Frontend contract ─────────────────────────
    pydantic_type = "str"
    js_behavior   = {"serialize": "str", "include_if": "always", "on_change": ""}
    js_inline     = None
    js_validation = None  # o ej. {"required": True} / {"enum": ["a","b"]} / {"min": 0}

    def _load_options(
        self,
        parent_values: Optional[Dict[str, Any]] = None,
    ) -> List[FilterOption]:
        static = self.config.ui_config.get("static_options", [])
        return [FilterOption(value=o["value"], label=o["label"]) for o in static]

    def validate(self, value: Any) -> bool:
        if value is None or value == "":
            return not self.config.required
        opts = self.get_options()
        return any(str(o.value) == str(value) for o in opts)

    def get_default(self) -> Any:
        return self.config.default_value

    def to_sql_clause(self, value: Any) -> Optional[tuple[str, dict]]:
        if not value:
            return None
        col = self.config.param_name
        return f"{col} = :{col}", {col: value}
```

**Plantilla para filtro que carga opciones desde MetadataCache:**

```python
"""{NombreClase} — {descripción breve}."""
from __future__ import annotations
from typing import Any, Dict, List, Optional

from new_app.core.cache import metadata_cache
from new_app.services.filters.base import FilterOption, OptionsFilter


class {NombreClase}(OptionsFilter):
    """{Docstring}"""

    filter_type    = "dropdown"
    param_name     = "{param_name}"
    options_source = "{options_source}"   # clave en MetadataCache
    default_value  = None
    placeholder    = "{placeholder}"
    required       = False
    depends_on     = None   # o "line_id" para cascade
    ui_config      = {}

    # ── Frontend contract ─────────────────────────
    pydantic_type = "Any"
    js_behavior   = {"serialize": "raw", "include_if": "truthy", "on_change": ""}
    js_inline     = None
    js_validation = None  # o ej. {"required": True} / {"enum": ["a","b"]} / {"min": 0}

    def _load_options(
        self,
        parent_values: Optional[Dict[str, Any]] = None,
    ) -> List[FilterOption]:
        items = metadata_cache.get_{options_source}()  # ajustar al método real
        return [
            FilterOption(value=k, label=v["nombre_campo"])
            for k, v in items.items()
        ]

    def validate(self, value: Any) -> bool:
        if value is None or value == "":
            return not self.config.required
        opts = self.get_options()
        return any(o.value == value or str(o.value) == str(value) for o in opts)

    def get_default(self) -> Any:
        return self.config.default_value

    def to_sql_clause(self, value: Any) -> Optional[tuple[str, dict]]:
        if not value:
            return None
        col = self.config.param_name
        return f"{col} = :{col}", {col: value}
```

---

### Paso 2 — Registrar en la tabla `filter` (DB Tenant)

Ejecutar en la DB del tenant correspondiente:

```sql
INSERT INTO filter (filter_name, additional_filter, is_active)
VALUES ('{NombreClase}', NULL, 1);
```

> `filter_name` debe coincidir **exactamente** con el nombre de la clase Python.
> Anotar el `filter_id` generado — se necesita en el Paso 4.

---

> **⚡ Los pasos 3, 4 y 5 del flujo clásico YA NO EXISTEN.**
>
> - El modelo Pydantic (`DashboardDataRequest`) se construye **dinámicamente** en
>   `new_app/api/v1/schemas/dynamic_request.py` a partir del `pydantic_type` declarado
>   en cada clase de filtro. No editar ese archivo.
> - `build_filter_dict()` descubre los `param_name`s automáticamente desde
>   `filter_engine.get_all_classes()`. No editar `request_helpers.py`.
> - `_buildRequestBody()` en JS itera `ctx.filterStates` usando los atributos
>   `js_behavior` de cada clase de filtro. No agregar código en
>   `dashboard-orchestrator.js`.
> - `_validateParamsLocally()` en JS lee `filterStates[param].validation` (propagado
>   desde `js_validation` de la clase). No agregar código en `dashboard-orchestrator.js`.
>
> **Lo que controla el comportamiento frontend/backend está 100% en los atributos
> `pydantic_type`, `js_behavior`, `js_inline` y `js_validation` declarados en el Paso 1.**

---

### Paso 3 — Declarar `js_validation` en la clase del filtro (si aplica)

**Archivo:** `new_app/services/filters/types/{nombre_clase_snake}.py` — el mismo del Paso 1.

Solo si el filtro necesita validación en el browser antes de enviar la query.
Agregar el atributo `js_validation` en la sección «Frontend contract»:

```python
# ── Frontend contract ─────────────────────────
pydantic_type = "str"
js_behavior   = {"serialize": "str", "include_if": "always", "on_change": ""}
js_inline     = None
js_validation = {"required": True, "required_msg": "Este campo es obligatorio"}
```

**Reglas disponibles** (se pueden combinar en el mismo dict):

| Clave | Tipo | Efecto |
|---|---|---|
| `required` | `True` | Error si el valor es `null`, `undefined` o `""` |
| `required_msg` | `str` | Mensaje de error personalizado para `required` |
| `enum` | `list` | Error si el valor no está en la lista |
| `enum_msg` | `str` | Mensaje personalizado para `enum` |
| `min` | `number` | Error si el valor numérico es menor que este |
| `min_msg` | `str` | Mensaje personalizado para `min` |
| `type: "daterange"` | especial | Valida el objeto `{start_date, end_date}` completo |

> **No editar `dashboard-orchestrator.js`.** `_validateParamsLocally()` ya itera
> `filterStates` genéricamente y aplica estas reglas de forma automática.
>
> Omitir `js_validation` (o dejarlo `None`) para filtros opcionales sin restricciones.

---

### Paso 4 — Asignar el filtro al `dashboard_template` en DB

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
| 1 | `services/filters/types/{nombre}.py` | Crear clase con `pydantic_type`, `js_behavior`, `js_validation`, `to_sql_clause` | ✅ |
| 2 | DB `filter` | `INSERT` con `filter_name` | ✅ |
| 3 | `services/filters/types/{nombre}.py` → `js_validation` | Declarar reglas de validación browser (si aplica) | ⚠️ |
| 4 | DB `dashboard_template` | Agregar `filter_id` al layout | ✅ |

> **No editar:** `api/v1/schemas/dynamic_request.py`, `utils/request_helpers.py`, `_buildRequestBody` ni `_validateParamsLocally` en JS — se auto-configuran desde los atributos de la clase.

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

    # ── Layout del grid (posición y visibilidad) ──────────────
    tab           = "{tab}"          # "produccion" | "oee"
    col_span      = {col_span}       # 1–4
    row_span      = {row_span}       # 1–2 (omitir si es 1)
    order         = {order}          # único: buscar el último en los tipos existentes
    downtime_only = {downtime_only}  # True si ocultar en multi-línea

    # ── Renderizado ─────────────────────────────────────────
    required_columns = ["{col1}", "{col2}"]
    default_config   = {}
    render           = "{render}"      # "kpi" | "chart" | "table" | etc.
    chart_type       = "{chart_type}"  # "" si no es chart
    chart_height     = "{chart_height}"

    # ── js_inline: solo si render = "chart" ───────────────────
    # Omitir completamente si render != "chart"
    js_inline = """
(function() {
  window.WidgetChartBuilders = window.WidgetChartBuilders || {};
  window.WidgetChartBuilders['{NombreClase}'] = function(data, params, utils) {
    // data: payload retornado por process()
    // params: filtros activos del dashboard
    // utils: helpers de chart-config.js (_cssVar, _curveProps, buildDowntimeAnnotations, etc.)
    return {
      type: '{chart_js_type}',   // 'line' | 'bar' | 'pie' | 'scatter'
      data: {
        labels: data.labels || [],
        datasets: [/* ... */],
      },
      options: {
        responsive: true,
        // ... opciones Chart.js
        plugins: {
          annotation: { annotations: utils.buildDowntimeAnnotations(data.downtime_events || []) },
        },
        ...utils._zoomOptions(true),
      },
    };
  };
})();
"""

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

### Paso 3 — Asignar al `dashboard_template` en DB

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

> El layout (tab, col_span, order, etc.) ya fue declarado **directamente en la clase**
> en el Paso 1. No se necesita ningún archivo de configuración externo.

---

### ✅ Checklist de Widget

| # | Archivo | Acción | Crítico |
|---|---------|--------|---------|
| 1 | `services/widgets/types/{nombre}.py` | Crear clase con layout attrs, `process()`, y `js_inline` si es chart | ✅ |
| 2 | DB Global `widget_catalog` | `INSERT` con `widget_name` | ✅ |
| 3 | DB Tenant `dashboard_template` | Agregar `widget_id` al layout | ✅ |

---

---

## REGLAS DE NAMING (resumen rápido)

```
NombreClase   →  nombre_clase.py   (archivo)
NombreClase   →  nombre_clase      (clave en DB widget_name / filter_name)
param_name    →  ctx.filterStates['{param_name}'].value  (Alpine.js / JS)
param_name    →  body.{param_name}        (HTTP body, auto-serializado)
param_name    →  req.{param_name}         (Pydantic)
param_name    →  cleaned["{param_name}"]  (FilterEngine)
```

---

## FLUJO DE DATOS (recordatorio)

### Filtro

```
Usuario selecciona valor en UI
    → Alpine: ctx.filterStates['{param_name}'].value = valor
    → _buildRequestBody(): serializa según js_behavior.serialize/include_if  [auto]
    → HTTP POST body
    → DashboardDataRequest.{param_name}  (campo auto-generado por pydantic_type)  [auto]
    → build_filter_dict() → cleaned['{param_name}']  (auto via get_all_classes)  [auto]
    → FilterEngine.validate_input() → cleaned
    → {NombreClase}.to_sql_clause(valor)                   [Paso 1]
    → WHERE {columna} = :{param_name}
```

### Widget

```
Pipeline ejecuta
    → WidgetEngine descubre {nombre_clase}.py              [Paso 1]
    → DataBroker slicea df a required_columns
    → {NombreClase}(ctx).process() → WidgetResult
    → ResponseAssembler incluye widget_id                  [Paso 3]
    → Frontend renderiza con template _widget_{render}.html
    → ChartRenderer busca WidgetChartBuilders['{NombreClase}']
      y llama al builder registrado en js_inline           [Paso 1 — solo charts]
```
