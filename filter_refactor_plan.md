# Plan de Implementación — Filter System Refactor

> **Principio guía:** En ningún punto intermedio del plan el sistema debe quedar roto.
> Cada fase puede desplegarse de forma independiente y el dashboard sigue funcionando.

---

## Mapa de dependencias

```
FASE 1 ──► FASE 2 ──► FASE 3 ──► FASE 4 ──► FASE 5
(base.py)  (filtros)  (engine)   (backend)  (frontend)
                                              │
                                              └──► FASE 6 (templates)
                                              └──► FASE 7 (cleanup)
```

Fases 1–4 son **solo Python**, sin tocar JS ni templates.
La app sigue funcionando con los filtros viejos durante toda esta etapa.
Fase 5–6 migra el frontend. Fase 7 elimina código muerto.

---

## FASE 1 — Contratos nuevos en `base.py`
**Archivos:** 1 | **Riesgo:** Bajo (solo agrega atributos, no rompe nada)

### `new_app/services/filters/base.py` — Cambios

**1a. Agregar a `FilterConfig` dataclass:**
```python
# Después del campo ui_config existente, agregar:
pydantic_type: str = "Any"
js_behavior: Dict[str, str] = field(default_factory=lambda: {
    "serialize": "raw",
    "include_if": "truthy",
    "on_change": "",
})
```

**1b. Agregar `to_dict()` en `FilterConfig`** los nuevos campos:
```python
def to_dict(self) -> Dict[str, Any]:
    return {
        # ... campos existentes sin cambios ...
        "pydantic_type": self.pydantic_type,   # NUEVO
        "js_behavior":   self.js_behavior,      # NUEVO
    }
```

**1c. Agregar a `BaseFilter` los tres nuevos atributos de clase:**
```python
class BaseFilter(ABC):
    # ... atributos existentes sin cambios ...

    # NUEVOS:
    pydantic_type : str            = "Any"
    js_behavior   : Dict[str,str]  = {
        "serialize":  "raw",
        "include_if": "truthy",
        "on_change":  "",
    }
    js_inline     : Optional[str]  = None
```

**1d. Actualizar `FilterEngine.get_all()`** para leer los nuevos atributos al construir `FilterConfig`:
```python
config = FilterConfig(
    # ... campos existentes ...
    pydantic_type = cls.pydantic_type,   # NUEVO
    js_behavior   = dict(cls.js_behavior), # NUEVO (copy)
)
```

**1e. `OptionsFilter` e `InputFilter` permanecen intactos** — no se eliminan en esta fase.
Los filtros concretos existentes siguen heredando de ellos sin tocarlos.

### ✅ Checkpoint Fase 1
- `pytest` en verde
- Dashboard carga y funciona igual que antes
- `filter_engine.resolve_all()` retorna `pydantic_type` y `js_behavior` en cada filtro

---

## FASE 2 — Migración de filtros concretos
**Archivos:** 10 | **Riesgo:** Bajo por filtro (son independientes entre sí)

Cada filtro se migra de forma atómica. El orden no importa —
la herencia vieja sigue funcionando para los que aún no migraron.

### Patrón de migración por filtro

```
ANTES:
class ShiftFilter(DropdownFilter):
    filter_type = "dropdown"
    param_name  = "shift_id"
    # sin pydantic_type, sin js_behavior, sin js_inline

DESPUÉS:
class ShiftFilter(BaseFilter):          # ← herencia directa
    filter_type   = "dropdown"
    param_name    = "shift_id"
    pydantic_type = "int"               # NUEVO
    js_behavior   = {                   # NUEVO
        "serialize":  "int",
        "include_if": "truthy",
        "on_change":  "onShiftChange",
    }
    js_inline = """..."""               # NUEVO — handler JS
    # + _load_options() copiado desde DropdownFilter/_LOADERS
    # + validate(), get_default(), to_sql_clause() propios
```

### Tabla de migración — 10 filtros

| Archivo | Herencia actual | Nueva herencia | `pydantic_type` | `serialize` | `include_if` | `on_change` | `js_inline` |
|---|---|---|---|---|---|---|---|
| `date_range_filter.py` | `InputFilter` | `BaseFilter` | `Dict[str,str]` | `daterange` | `not_null` | — | `validateEndDate`, `validateEndTime` |
| `production_line_filter.py` | `DropdownFilter` | `BaseFilter` | `Any` | `line_id` | `truthy` | `onLineChange` | `onLineChange` + fetch areas |
| `shift_filter.py` | `DropdownFilter` | `BaseFilter` | `int` | `int` | `truthy` | `onShiftChange` | `onShiftChange` |
| `product_filter.py` | `MultiselectFilter` | `BaseFilter` | `List[int]` | `array_int` | `array_not_empty` | `onProductIdsChange` | `onProductIdsChange`, `toggleProduct` |
| `area_filter.py` | `MultiselectFilter` | `BaseFilter` | `List[int]` | `array_int` | `array_not_empty` | — | — |
| `interval_filter.py` | `DropdownFilter` | `BaseFilter` | `str` | `str` | `always` | `onIntervalChange` | `onIntervalChange` |
| `curve_type_filter.py` | `DropdownFilter` | `BaseFilter` | `str` | `str` | `always` | `onCurveTypeChange` | `onCurveTypeChange` |
| `downtime_threshold_filter.py` | `InputFilter` | `BaseFilter` | `int` | `int` | `not_null` | — | — |
| `show_downtime_filter.py` | `ToggleFilter` | `BaseFilter` | `bool` | `bool` | `truthy` | `onShowDowntimeChange` | `onShowDowntimeChange` |
| `search_filter.py` | `InputFilter` | `BaseFilter` | `str` | `str` | `truthy` | `onSearchChange` | `onSearchChange` |

### Detalle de cada migración

#### `date_range_filter.py`
- Copiar `validate()` y `parse_datetimes()` y `to_sql_clause()` del archivo actual (sin cambios lógicos)
- Copiar `get_default()` del archivo actual
- `js_inline`: mover `validateEndDate()` y `validateEndTime()` desde `dashboard-events.js`

#### `production_line_filter.py`
- Copiar `_load_production_lines()` desde `dropdown.py` (el loader de grupos)
- `to_sql_clause()`: copiar lógica de grupos (line_id vs line_ids) del actual
- `js_inline`: mover `onLineChange()` desde `dashboard-app.js` + fetchAreas

#### `shift_filter.py`
- Copiar `_load_shifts()` desde `dropdown.py`
- `to_sql_clause()` retorna `None` (shift es client-side)
- `js_inline`: mover `onShiftChange()` desde `dashboard-events.js`

#### `product_filter.py`
- Copiar `_load_products()` desde `dropdown.py`
- `to_sql_clause()`: `product_id IN :product_ids`
- `js_inline`: mover `onProductIdsChange()` + agregar `toggleProduct()`

#### `area_filter.py`
- Copiar `_load_areas()` desde `dropdown.py` (con filtrado por `line_id`)
- `to_sql_clause()`: `area_id IN :area_ids`
- Sin `js_inline` (no tiene handler especial)

#### `interval_filter.py`
- Opciones estáticas inline (minuto/hora/día/semana/mes)
- `to_sql_clause()` retorna `None` (es para agregación client-side)
- `js_inline`: mover `onIntervalChange()` desde `dashboard-events.js`

#### `curve_type_filter.py`
- Opciones estáticas inline (smooth/linear/step)
- `to_sql_clause()` retorna `None`
- `js_inline`: mover `onCurveTypeChange()` desde `dashboard-events.js`

#### `downtime_threshold_filter.py`
- Sin opciones
- `to_sql_clause()` retorna `None` (se usa en downtime_calculator)
- Sin `js_inline`

#### `show_downtime_filter.py`
- Sin opciones
- `to_sql_clause()` retorna `None`
- `js_inline`: mover `onShowDowntimeChange()` desde `dashboard-events.js`

#### `search_filter.py`
- Sin opciones
- `to_sql_clause()` retorna `None` (client-side)
- `js_inline`: mover `onSearchChange()` desde `dashboard-events.js`

### ✅ Checkpoint Fase 2
- Cada filtro migrado mantiene comportamiento idéntico al anterior
- `filter_engine.resolve_all()` retorna `js_behavior` correcto para cada filtro
- `pytest` en verde
- Dashboard funciona sin cambios visibles

---

## FASE 3 — FilterEngine: agregar `get_all_classes()`
**Archivos:** 1 | **Riesgo:** Muy bajo (solo agrega método nuevo)

### `new_app/services/filters/engine.py`

Agregar método nuevo. No modifica ningún método existente.

```python
def get_all_classes(self) -> List[Type[BaseFilter]]:
    """
    Return all active filter classes (not instances).
    Used by: dynamic Pydantic model, generic build_filter_dict.
    Order matches display_order from DB.
    """
    cached_filters = metadata_cache.get_filters()
    classes: List[Type[BaseFilter]] = []
    seen: set = set()

    for _fid, row in sorted(
        cached_filters.items(),
        key=lambda kv: kv[1].get("display_order", 99)
    ):
        class_name = row["filter_name"]
        if class_name in seen:
            continue
        cls = self._get_class(class_name)
        if cls is not None:
            classes.append(cls)
            seen.add(class_name)

    return classes
```

### ✅ Checkpoint Fase 3
- `filter_engine.get_all_classes()` retorna lista de clases con sus nuevos atributos

---

## FASE 4 — Backend: modelo Pydantic dinámico + `build_filter_dict` genérico
**Archivos:** 3 | **Riesgo:** Medio (punto de integración entre Python y la API)

### 4a. Nuevo archivo: `new_app/api/v1/schemas/dynamic_request.py`

```python
"""
Auto-generates DashboardDataRequest from active filter classes.
No manual field declarations needed when adding a new filter.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, get_type_hints

from pydantic import BaseModel, Field, create_model

logger = logging.getLogger(__name__)

# Campos fijos del request (no son filtros — siempre presentes)
_FIXED_FIELDS = {
    "widget_ids":   (Optional[List[int]], Field(None)),
    "include_raw":  (bool,                Field(False)),
    "tenant_id":    (Optional[int],       Field(None, description="[DEPRECATED]")),
    "role":         (Optional[str],       Field(None, description="[DEPRECATED]")),
    "charts":       (Optional[Dict[str, str]], Field(None)),
}

# String → Python type mapping for pydantic_type attribute
_TYPE_MAP = {
    "Any":            Optional[Any],
    "int":            Optional[int],
    "str":            Optional[str],
    "bool":           Optional[bool],
    "List[int]":      Optional[List[int]],
    "List[str]":      Optional[List[str]],
    "Dict[str,str]":  Optional[Dict[str, str]],
}

_model_cache: Optional[type] = None


def build_dashboard_request_model() -> type:
    """
    Build DashboardDataRequest dynamically from active filter classes.

    Called once at startup (lazy, on first request to avoid cache
    not-loaded issues). Result is cached in _model_cache.
    """
    global _model_cache
    if _model_cache is not None:
        return _model_cache

    try:
        from new_app.services.filters.engine import filter_engine
        filter_classes = filter_engine.get_all_classes()
    except Exception as e:
        logger.error("[DynamicRequest] Could not load filter classes: %s", e)
        filter_classes = []

    fields: Dict[str, Any] = dict(_FIXED_FIELDS)

    for cls in filter_classes:
        python_type = _TYPE_MAP.get(cls.pydantic_type, Optional[Any])
        # Use the class default_value as the Pydantic field default
        default = cls.default_value if cls.default_value is not None else None
        fields[cls.param_name] = (python_type, Field(default))
        logger.debug(
            "[DynamicRequest] Field: %s (%s) default=%s",
            cls.param_name, cls.pydantic_type, default
        )

    _model_cache = create_model("DashboardDataRequest", **fields)
    logger.info(
        "[DynamicRequest] Model built with %d filter fields + %d fixed fields",
        len(filter_classes), len(_FIXED_FIELDS)
    )
    return _model_cache


def invalidate_model_cache() -> None:
    """Call after MetadataCache reload to force model rebuild."""
    global _model_cache
    _model_cache = None


# Lazy singleton — built on first access
def get_dashboard_request_model() -> type:
    return build_dashboard_request_model()
```

### 4b. `new_app/api/v1/schemas/__init__.py`

Cambiar la importación de `DashboardDataRequest`:

```python
# ANTES:
from new_app.api.v1.schemas.dashboard_schemas import DashboardDataRequest

# DESPUÉS:
from new_app.api.v1.schemas.dynamic_request import get_dashboard_request_model
DashboardDataRequest = get_dashboard_request_model()
```

> El archivo `dashboard_schemas.py` se deja intacto por ahora como fallback —
> se elimina en Fase 7.

### 4c. `new_app/utils/request_helpers.py`

Reemplazar `build_filter_dict` completamente:

```python
def build_filter_dict(req) -> Dict[str, Any]:
    """
    Extract filter params from a Pydantic request into a flat dict
    matching FilterEngine's expected user_params shape.

    Fully generic: discovers param_names from FilterEngine.
    Adding a new filter does NOT require touching this file.
    """
    try:
        from new_app.services.filters.engine import filter_engine
        known_params = {cls.param_name for cls in filter_engine.get_all_classes()}
    except Exception:
        # Fallback: include all non-None fields that aren't control fields
        known_params = None

    raw = req.model_dump()
    control_fields = {"widget_ids", "include_raw", "tenant_id", "role", "charts"}

    if known_params is not None:
        return {k: v for k, v in raw.items()
                if k in known_params and v is not None}
    else:
        return {k: v for k, v in raw.items()
                if k not in control_fields and v is not None}
```

### 4d. `new_app/api/v1/system.py` (o donde se maneja cache refresh)

Al refrescar la metadata cache, también invalidar el modelo Pydantic:

```python
from new_app.api.v1.schemas.dynamic_request import invalidate_model_cache

# En el endpoint de cache refresh:
await metadata_cache.reload(tenant_id)
filter_engine.clear_instance_cache()
invalidate_model_cache()   # NUEVO
```

### ✅ Checkpoint Fase 4
- `POST /api/v1/dashboard/data` acepta todos los params existentes
- `build_filter_dict()` retorna los mismos campos que antes
- Un filtro nuevo (solo con archivo .py + DB insert) ya aparece en el modelo Pydantic
- `pytest` en verde, incluyendo tests de integración del endpoint

---

## FASE 5 — Frontend: migración a `filterStates`
**Archivos:** 3 JS | **Riesgo:** Alto (el cambio más invasivo — hacerlo en rama separada)

### Estrategia: proxy de compatibilidad

Para no romper referencias a `params.X` que puedan existir en otras partes,
`filterStates` y `params` coexisten durante la transición:
`params` se convierte en un getter que lee desde `filterStates`.

### 5a. `new_app/static/js/dashboard-app.js`

**Reemplazar** el bloque `initialParams` y la propiedad `params` del state:

```javascript
// ── Build filterStates from config ────────────────────────
const filterStates = {};
filters.forEach(function(f) {
    let initialValue;
    switch (f.filter_type) {
        case 'multiselect': initialValue = Array.isArray(f.default_value)
                            ? f.default_value : []; break;
        case 'toggle':      initialValue = f.default_value !== undefined
                            ? f.default_value : false; break;
        case 'number':      initialValue = f.default_value !== undefined
                            ? f.default_value : null; break;
        case 'daterange':
            initialValue = f.default_value || {
                start_date: new Date(Date.now() - 7 * 86400000)
                            .toISOString().slice(0, 10),
                end_date:   new Date().toISOString().slice(0, 10),
                start_time: '00:00',
                end_time:   '23:59',
            };
            break;
        default:
            initialValue = (f.default_value !== null && f.default_value !== undefined)
                           ? f.default_value : null;
    }
    filterStates[f.param_name] = {
        value:      initialValue,
        type:       f.filter_type,
        serialize:  (f.js_behavior && f.js_behavior.serialize)  || 'raw',
        include_if: (f.js_behavior && f.js_behavior.include_if) || 'truthy',
        on_change:  (f.js_behavior && f.js_behavior.on_change)  || '',
        options:    f.options || [],
    };
});

// ── Alpine State ───────────────────────────────────────────
const state = {
    // ... propiedades existentes sin cambios ...

    filterStates: JSON.parse(JSON.stringify(filterStates)),
    _initialFilterStates: filterStates,

    // Proxy de compatibilidad — mantiene params.X funcionando
    // durante la transición hasta que los templates se migren
    get params() {
        const p = {};
        for (const [key, state] of Object.entries(this.filterStates)) {
            p[key] = state.value;
        }
        return p;
    },

    // ... resto del state sin cambios ...
```

> **Nota:** El getter `params` hace que `params.line_id`, `params.daterange`, etc.
> sigan funcionando en todos los lugares donde se leen — los templates, los eventos
> que aún no se migraron, etc. Solo se rompe si algo hace `params.X = value` (escritura).
> Esos casos se identifican y migran en Fase 6.

**Agregar método `resetFilters()`** actualizado:
```javascript
resetFilters() {
    for (const [key, initial] of Object.entries(this._initialFilterStates)) {
        if (this.filterStates[key]) {
            // Deep copy para evitar mutación del initial
            this.filterStates[key].value = JSON.parse(JSON.stringify(initial.value));
        }
    }
    this.isMultiLine = false;
    this.selectedLineGroup = null;
},
```

### 5b. `new_app/static/js/dashboard-orchestrator.js`

**Reemplazar `_buildRequestBody(ctx)` completo:**

```javascript
_buildRequestBody(ctx) {
    const body = { include_raw: true };

    for (const [param, state] of Object.entries(ctx.filterStates)) {
        try {
            const val   = state.value;
            const incl  = _shouldInclude(val, state.include_if);
            if (!incl) continue;

            const serialized = _serializeValue(val, state.serialize, ctx);
            if (serialized === undefined) continue;

            // line_id groups expand to line_ids
            if (state.serialize === 'line_id' && ctx.isMultiLine
                && ctx.selectedLineGroup) {
                body.line_ids = ctx.selectedLineGroup.join(',');
            } else {
                body[param] = serialized;
            }
        } catch(e) {
            console.error('[buildRequestBody] Error on param', param, e);
        }
    }

    return body;
},
```

**Agregar helpers** (al inicio del objeto `DashboardOrchestrator` o como funciones privadas):

```javascript
// ── Serialization helpers ─────────────────────────────────
function _shouldInclude(value, includeIf) {
    switch (includeIf) {
        case 'always':          return true;
        case 'not_null':        return value !== null && value !== undefined;
        case 'array_not_empty': return Array.isArray(value) && value.length > 0;
        case 'truthy':
        default:                return !!value;
    }
}

function _serializeValue(value, serialize, ctx) {
    switch (serialize) {
        case 'int':        return parseInt(value);
        case 'str':        return String(value);
        case 'bool':       return Boolean(value);
        case 'array_int':  return Array.isArray(value)
                                  ? value.map(Number)
                                  : [Number(value)];
        case 'array_str':  return Array.isArray(value)
                                  ? value.map(String)
                                  : [String(value)];
        case 'daterange':  return value;  // objeto {start_date,...} as-is
        case 'not_null':   return value;
        case 'line_id':    return value !== null ? parseInt(value) : undefined;
        case 'raw':
        default:           return value;
    }
}
```

**Actualizar `_validateParamsLocally(params)`:**
El método ya recibe `params` (que viene del getter proxy), así que
sigue funcionando sin cambios durante la transición.
Actualizar solo las referencias que lean `ctx.params.X` directamente
a `ctx.filterStates['X']?.value` para ser explícitos.

**Actualizar `_countActiveFilters()`:**
```javascript
_countActiveFilters(filterStates) {
    let count = 0;
    for (const [key, state] of Object.entries(filterStates)) {
        const v = state.value;
        if (v !== null && v !== '' && v !== false &&
            !(Array.isArray(v) && v.length === 0)) count++;
    }
    return count;
},
```

### 5c. `new_app/static/js/dashboard-events.js`

Los handlers que se movieron a `js_inline` se **mantienen en este archivo** por ahora.
Los que ya viven en `js_inline` serán el source of truth, pero los de `dashboard-events.js`
siguen ahí como respaldo hasta Fase 7.

La razón: los handlers en `js_inline` se inyectan en Fase 6. Si se eliminan de
`dashboard-events.js` ahora, habría un gap. Se eliminan en Fase 7 cuando
la inyección esté confirmada como funcionando.

**Única actualización necesaria ahora:** reemplazar referencias a `this.params.X = value`
con `this.filterStates['X'].value = value` en los handlers que modifican estado:

```javascript
// Ejemplo en onLineChange:
// ANTES: this.params.area_ids = [];
// DESPUÉS: if (this.filterStates['area_ids']) this.filterStates['area_ids'].value = [];
```

### ✅ Checkpoint Fase 5
- `filterStates` inicializa correctamente para todos los filtros incluyendo daterange
- `_buildRequestBody` genera el mismo body que antes (verificar con console.log)
- Botón Aplicar funciona end-to-end
- Reset funciona
- Cascade line→area funciona
- Multiselect productos/áreas funciona

---

## FASE 6 — Templates: bindings a `filterStates` + inyección JS inline
**Archivos:** ~7 templates + 1 ruta Flask | **Riesgo:** Medio (visual, fácil de verificar)

### 6a. `new_app/routes/dashboard.py` — Recopilar `js_inline`

```python
from new_app.services.filters.engine import filter_engine

# En la función de render del dashboard, antes del render_template:
inline_js_blocks = []
seen_handlers = set()

for flt in filter_engine.get_all(filter_ids=enabled_filter_ids):
    cls = type(flt)
    if cls.js_inline and cls.js_inline.strip():
        # Evitar duplicados si el mismo handler aparece en múltiples filtros
        block = cls.js_inline.strip()
        if block not in seen_handlers:
            inline_js_blocks.append(block)
            seen_handlers.add(block)

return render_template(
    "dashboard/index.html",
    # ... vars existentes ...
    filter_inline_js=",\n".join(inline_js_blocks),  # comma-separated JS methods
)
```

### 6b. `new_app/templates/dashboard/index.html` — Inyectar handlers

Agregar bloque al final del script de Alpine (antes del cierre `</script>`):

```html
{% if filter_inline_js %}
<script>
// ── Filter Handlers — auto-injected from filter class js_inline ──
(function() {
    'use strict';
    try {
        // Extend dashboardApp with filter-specific handlers
        const _filterHandlers = {
            {{ filter_inline_js | safe }}
        };
        const _original = window.dashboardApp;
        window.dashboardApp = function() {
            return Object.assign(_original(), _filterHandlers);
        };
    } catch(e) {
        console.error('[FilterHandlers] Failed to inject handlers:', e);
    }
})();
</script>
{% endif %}
```

### 6c. Actualizar templates de filtros — bindings a `filterStates`

#### `_filter_daterange.html`
```html
{# ANTES: x-model="params.daterange.start_date" #}
{# DESPUÉS: #}
<input type="date"
    :value="filterStates['daterange']?.value?.start_date"
    @input="filterStates['daterange'].value.start_date = $event.target.value; validateEndDate()"
    :max="filterStates['daterange']?.value?.end_date || ''">

<input type="date"
    :value="filterStates['daterange']?.value?.end_date"
    @input="filterStates['daterange'].value.end_date = $event.target.value; validateEndDate()"
    :min="filterStates['daterange']?.value?.start_date || ''">

<input type="time"
    :value="filterStates['daterange']?.value?.start_time"
    @input="filterStates['daterange'].value.start_time = $event.target.value; validateEndTime()">

<input type="time"
    :value="filterStates['daterange']?.value?.end_time"
    @input="filterStates['daterange'].value.end_time = $event.target.value; validateEndTime()">
```

#### `_filter_dropdown.html`
```html
{# ANTES: x-model="params.{{ f.param_name }}" @change="..." #}
{# DESPUÉS: #}
<select
    :value="filterStates['{{ f.param_name }}']?.value"
    @change="
        filterStates['{{ f.param_name }}'].value = $event.target.value || null;
        const handler = filterStates['{{ f.param_name }}'].on_change;
        if (handler && typeof $data[handler] === 'function') {
            $data[handler]($event.target.value);
        }
    ">
```

#### `_filter_multiselect.html`
```html
{# ANTES: @change="toggleMultiselect(...)" :checked="params.X.includes(...)" #}
{# DESPUÉS: #}
<input type="checkbox"
    :value="opt.value"
    :checked="(filterStates['{{ f.param_name }}']?.value || []).includes(opt.value)"
    @change="
        const arr = filterStates['{{ f.param_name }}'].value;
        const idx = arr.indexOf(opt.value);
        if (idx === -1) arr.push(opt.value);
        else arr.splice(idx, 1);
        const handler = filterStates['{{ f.param_name }}'].on_change;
        if (handler && typeof $data[handler] === 'function') {
            $data[handler]();
        }
    ">
```

#### `_filter_toggle.html`
```html
{# ANTES: @click="params.X = !params.X; onShowDowntimeChange()" #}
{# DESPUÉS: #}
<button type="button"
    @click="
        filterStates['{{ f.param_name }}'].value =
            !filterStates['{{ f.param_name }}'].value;
        const handler = filterStates['{{ f.param_name }}'].on_change;
        if (handler && typeof $data[handler] === 'function') {
            $data[handler]();
        }
    "
    :class="filterStates['{{ f.param_name }}']?.value
            ? 'bg-accent-500' : 'bg-surface-700'">
    <span :class="filterStates['{{ f.param_name }}']?.value
                  ? 'translate-x-5' : 'translate-x-0.5'">
    </span>
</button>
```

#### `_filter_number.html`
```html
{# ANTES: x-model.number="params.X" #}
{# DESPUÉS: #}
<input type="number"
    :value="filterStates['{{ f.param_name }}']?.value"
    @input="filterStates['{{ f.param_name }}'].value =
            $event.target.value !== '' ? Number($event.target.value) : null">
```

#### `_filter_text.html`
```html
{# ANTES: x-model="params.X" @input="onSearchChange()" #}
{# DESPUÉS: #}
<input type="text"
    :value="filterStates['{{ f.param_name }}']?.value || ''"
    @input="
        filterStates['{{ f.param_name }}'].value = $event.target.value || null;
        const handler = filterStates['{{ f.param_name }}'].on_change;
        if (handler && typeof $data[handler] === 'function') {
            $data[handler]();
        }
    ">
```

### ✅ Checkpoint Fase 6
- Todos los filtros visualmente iguales a antes
- Handlers especiales funcionan (cascade, re-agg, validación de fechas)
- No hay referencias a `params.X =` (escritura) fuera de `filterStates`
- Body del request es idéntico al pre-refactor (verificar en Network tab)

---

## FASE 7 — Limpieza: eliminar código muerto
**Archivos:** ~5 | **Riesgo:** Bajo (solo eliminar código que ya no se usa)

**Ejecutar antes:** `grep -r "DropdownFilter\|MultiselectFilter\|ToggleFilter\|InputFilter" new_app/`
para confirmar que no hay importaciones restantes.

### 7a. Eliminar clases base intermedias

```
ELIMINAR: new_app/services/filters/types/dropdown.py
ELIMINAR: new_app/services/filters/types/multiselect.py
ELIMINAR: new_app/services/filters/types/toggle.py
```

`InputFilter` y `OptionsFilter` en `base.py` — dejarlos como stubs deprecados
con un comentario claro, o eliminarlos si grep confirma que no hay referencias.

### 7b. Eliminar handlers de `dashboard-events.js` ya migrados a `js_inline`

Los siguientes métodos se eliminan de `dashboard-events.js` porque ahora viven
en el `js_inline` de su filtro correspondiente:
- `validateEndDate()`, `validateEndTime()` → `DateRangeFilter.js_inline`
- `onShiftChange()` → `ShiftFilter.js_inline`
- `onProductIdsChange()` → `ProductFilter.js_inline`
- `onIntervalChange()` → `IntervalFilter.js_inline`
- `onCurveTypeChange()` → `CurveTypeFilter.js_inline`
- `onShowDowntimeChange()` → `ShowDowntimeFilter.js_inline`
- `onSearchChange()` → `SearchFilter.js_inline`

> `_debouncedApply()` y `toggleWidgetMode()` permanecen en `dashboard-events.js`
> (no pertenecen a ningún filtro específico).

### 7c. Eliminar `dashboard_schemas.py`

Una vez confirmado que `dynamic_request.py` funciona en producción:
```
ELIMINAR: new_app/api/v1/schemas/dashboard_schemas.py
```

### 7d. Eliminar handlers de `dashboard-app.js` ya migrados a `js_inline`

Eliminar `onLineChange()` del state de Alpine en `dashboard-app.js`
(ahora vive en `ProductionLineFilter.js_inline`).

### 7e. Actualizar documentación

- `AGENT_ADD_WIDGET_FILTER.md`: reemplazar el checklist de 7 pasos por 2 pasos
- `WIDGETS_AND_FILTERS.md`: actualizar tabla de clases base y ejemplo de nuevo filtro
- `Documentation.md`: actualizar diagrama de arquitectura

### ✅ Checkpoint Fase 7
- `grep` no encuentra importaciones de clases eliminadas
- `pytest` en verde
- Dashboard funciona sin cambios visibles
- Agregar un filtro de prueba nuevo toca solo 1 archivo Python + 1 SQL

---

## Resumen ejecutivo

| Fase | Qué | Archivos | Riesgo | Puede deployarse solo |
|---|---|---|---|---|
| 1 | Nuevos atributos en `BaseFilter` | 1 | Muy bajo | ✅ |
| 2 | Migrar 10 filtros concretos | 10 | Bajo | ✅ (de a uno) |
| 3 | `get_all_classes()` en engine | 1 | Muy bajo | ✅ |
| 4 | Modelo Pydantic dinámico | 3 | Medio | ✅ |
| 5 | `filterStates` en Alpine | 3 JS | Alto | ⚠️ en rama separada |
| 6 | Templates + inyección JS | ~8 | Medio | ✅ después de Fase 5 |
| 7 | Eliminar código muerto | ~5 | Bajo | ✅ después de Fase 6 |

**Total estimado:** 12–15 horas de trabajo efectivo distribuidas en ~3 sesiones.

**Orden de sesiones sugerido:**
- Sesión 1: Fases 1 + 2 + 3 (todo Python puro, sin riesgo)
- Sesión 2: Fase 4 (backend API — verificar con Postman/pytest)
- Sesión 3: Fases 5 + 6 + 7 (frontend + cleanup)

---

## Plantilla para filtro nuevo post-refactor

Una vez completado el refactor, este es el único archivo que se crea:

```python
# new_app/services/filters/types/mi_filtro.py
"""MiFiltro — descripción."""
from __future__ import annotations
from typing import Any, List, Optional
from new_app.services.filters.base import BaseFilter, FilterOption

class MiFiltro(BaseFilter):
    filter_type   = "dropdown"      # dropdown|multiselect|toggle|number|text|daterange
    param_name    = "mi_param"      # snake_case, único
    default_value = None
    placeholder   = "Seleccionar..."
    required      = False
    depends_on    = None
    ui_config     = {}

    pydantic_type = "str"           # Any|int|str|bool|List[int]|List[str]|Dict[str,str]
    js_behavior   = {
        "serialize":  "str",        # int|str|bool|array_int|array_str|daterange|line_id|raw
        "include_if": "truthy",     # always|not_null|truthy|array_not_empty
        "on_change":  "",           # nombre de método Alpine, o "" para setter genérico
    }
    js_inline = None                # JS handler si necesita lógica especial

    def validate(self, value: Any) -> bool:
        return value is None or isinstance(value, str)

    def get_default(self) -> Any:
        return None

    def get_options(self, parent_values=None) -> List[FilterOption]:
        return [
            FilterOption("val1", "Opción 1"),
            FilterOption("val2", "Opción 2"),
        ]

    def to_sql_clause(self, value: Any):
        if not value: return None
        return "mi_columna = :mi_param", {"mi_param": value}
```

Y el SQL:
```sql
INSERT INTO filter (filter_name, is_active) VALUES ('MiFiltro', 1);
-- Agregar filter_id al layout_config del dashboard_template
```

**Cero archivos de código adicionales.**