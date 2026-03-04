# Plan de Implementación — Widget System Refactor

> **Objetivo:** Cada widget es completamente autocontenido en su archivo `.py`.
> Agregar un widget nuevo = 1 archivo + 1 `INSERT` en DB. Cero archivos adicionales.
>
> **Decisiones tomadas:**
> - Layout (tab, col_span, order, downtime_only) → atributos de clase, `widget_layout.py` eliminado
> - JS chart config → `js_inline` define el config completo de Chart.js por widget
> - `recomputeFromRaw` → sin cambios, DashboardDataEngine permanece genérico
> - `display_name` / `description` → siguen en DB únicamente
> - Los 18 widgets existentes migran todos en este refactor

---

## Mapa de dependencias

```
FASE 1 ──► FASE 2 ──► FASE 3 ──► FASE 4 ──► FASE 5 ──► FASE 6 ──► FASE 7
(base.py)  (engine)  (route)   (widgets)  (inyección) (ChartRend) (cleanup)
                                            │
                                    (5 chart widgets
                                     + 13 non-chart)
```

Fases 1–3 son preparación de infraestructura. Fase 4 migra los 18 widgets.
Fases 5–7 conectan el frontend. La app funciona en todo momento intermedio.

---

## Contexto: qué cambia y qué no

### Lo que CAMBIA
| Componente | Antes | Después |
|---|---|---|
| `BaseWidget` | `render`, `chart_type`, `chart_height` | + `tab`, `col_span`, `row_span`, `order`, `downtime_only`, `js_inline` |
| `widget_layout.py` | fuente de layout | **eliminado** |
| `routes/dashboard.py` `_enrich_widgets()` | lee WIDGET_LAYOUT | lee clase via WidgetEngine |
| `chart-config.js` `ChartConfigBuilder` | dispatcher central (switch) | biblioteca de utilidades compartidas |
| `chart-renderer.js` `ChartRenderer.render()` | llama `ChartConfigBuilder.getConfig()` | chequea `WidgetChartBuilders[name]` primero |
| `_renderTabCharts()` | filtra por `meta.chart_type` | filtra por presencia en `WidgetChartBuilders` |

### Lo que NO CAMBIA
- `WidgetEngine.process_widgets()` — sin tocar
- `WidgetContext`, `WidgetResult` — sin tocar
- `DashboardDataEngine.recomputeFromRaw` — sin tocar
- Schemas de datos por `render` type (kpi, chart, table, etc.) — sin tocar
- Templates Jinja2 de widgets (`_widget_kpi.html`, etc.) — sin tocar
- Todas las tablas DB — sin tocar

---

## El contrato de `js_inline` para widgets chart

La pieza central del diseño. Cada widget con `render = "chart"` declara un
bloque JS que registra su builder en el objeto global `WidgetChartBuilders`:

```javascript
// Formato canónico del js_inline de un widget chart:
WidgetChartBuilders['MiWidgetChart'] = {
    zoomable:   true,   // si crear zoom toolbar
    toggleable: false,  // si soporta toggle line/bar (solo line_chart)
    buildConfig: function(data, options) {
        // options = { resetBtn, isMultiLine, mode, widgetId }
        // Puede usar ChartConfigBuilder como librería de utilidades:
        //   ChartConfigBuilder._tooltipDefaults()
        //   ChartConfigBuilder._zoomOptions(resetBtn)
        //   ChartConfigBuilder._cssVar('--chart-line-1', '#22c55e')
        //   ChartConfigBuilder.buildDowntimeAnnotations(events)
        return {
            type: 'line',
            data: { ... },
            options: { ... },
        };
    },
};
```

Para widgets que NO son chart (kpi, table, indicator, feed, etc.):
```python
js_inline = None  # sin bloque JS
```

---

## FASE 1 — Nuevos atributos en `BaseWidget`
**Archivos:** 1 | **Riesgo:** Muy bajo

### `new_app/services/widgets/base.py`

**Cambios en la clase `BaseWidget`** — solo agregar atributos, sin tocar nada existente:

```python
class BaseWidget(ABC):
    # ── Existentes (sin cambios) ──────────────────────────────────
    required_columns : List[str]       = []
    default_config   : Dict[str, Any]  = {}
    render           : str             = "kpi"
    chart_type       : str             = ""
    chart_height     : str             = "250px"

    # ── NUEVO: Layout (reemplaza widget_layout.py) ────────────────
    # Estos atributos son la fuente de verdad del posicionamiento visual.
    # El widget sabe dónde vive — no hay que buscarlo en un dict externo.
    tab          : str  = "produccion"  # "produccion" | "oee"
    col_span     : int  = 1             # 1–4 (grid de 4 columnas)
    row_span     : int  = 1             # 1–2 filas
    order        : int  = 0             # orden en el grid
    downtime_only: bool = False         # ocultar en modo multi-línea

    # ── NUEVO: JS inline (Chart.js config + handlers) ────────────
    # Para widgets chart: registra el buildConfig en WidgetChartBuilders.
    # Para widgets no-chart: None.
    js_inline: Optional[str] = None
```

**Agregar método `get_layout()` a `BaseWidget`** — retorna el dict que
`_enrich_widgets` necesita para construir el grid:

```python
@classmethod
def get_layout(cls) -> Dict[str, Any]:
    """
    Return layout metadata as dict — replaces WIDGET_LAYOUT lookup.
    Called by routes/dashboard.py _enrich_widgets().
    """
    return {
        "tab":          cls.tab,
        "col_span":     cls.col_span,
        "row_span":     cls.row_span,
        "order":        cls.order,
        "downtime_only": cls.downtime_only,
        "render":       cls.render,
        "chart_type":   cls.chart_type,
        "chart_height": cls.chart_height,
    }
```

### ✅ Checkpoint Fase 1
- `pytest` verde
- Un widget existente puede llamar `KpiOee.get_layout()` — retorna defaults
- Dashboard funciona sin cambios (WIDGET_LAYOUT aún en uso)

---

## FASE 2 — `WidgetEngine`: exponer clases sin instanciar
**Archivos:** 1 | **Riesgo:** Muy bajo

### `new_app/services/widgets/engine.py`

Agregar dos métodos nuevos. No modifica nada existente.

```python
def get_class(self, class_name: str) -> Optional[Type[BaseWidget]]:
    """
    Return the widget class for a given class_name.
    Used by _enrich_widgets() in routes/dashboard.py to read
    layout attributes without instantiating the widget.
    """
    return self._resolve_class(class_name)

def get_js_inline_blocks(
    self,
    widget_names: List[str],
) -> str:
    """
    Collect all non-None js_inline blocks from the given widgets.
    Returns a single JS string ready to inject in the template.
    Deduplicates in case the same class appears twice.
    Each block is wrapped in a try/catch for silent error isolation.
    """
    seen: set = set()
    blocks: List[str] = []

    for name in widget_names:
        if name in seen:
            continue
        seen.add(name)
        cls = self._resolve_class(name)
        if cls is None or not cls.js_inline:
            continue
        block = cls.js_inline.strip()
        # Wrap in try/catch to isolate widget JS errors
        safe_block = (
            f"try {{\n{block}\n}}"
            f" catch(e) {{ console.error('[{name}] js_inline error:', e); }}"
        )
        blocks.append(safe_block)

    return "\n\n".join(blocks)
```

### ✅ Checkpoint Fase 2
- `widget_engine.get_class('KpiOee')` retorna la clase
- `widget_engine.get_js_inline_blocks(['ProductionTimeChart'])` retorna `""` (aún sin js_inline en las clases)

---

## FASE 3 — `routes/dashboard.py`: leer layout desde clases
**Archivos:** 1 | **Riesgo:** Bajo

### `_enrich_widgets()` — reemplazar lookup de WIDGET_LAYOUT

**Estrategia dual durante transición:** intenta leer desde la clase primero,
cae al WIDGET_LAYOUT como fallback. Una vez todos los widgets migrados (Fase 4),
el fallback nunca se usa y se puede eliminar.

```python
# NUEVO import
from new_app.services.widgets.engine import widget_engine

def _enrich_widgets(widgets_data: list) -> None:
    """
    Add frontend rendering metadata to each widget dict.
    Reads layout from widget class attributes (via WidgetEngine).
    Falls back to WIDGET_LAYOUT for classes not yet migrated.
    Mutates widgets_data in place.
    """
    for idx, w in enumerate(widgets_data):
        if not isinstance(w, dict):
            continue
        class_name = w.get("widget_name", "")

        # ── Try class attributes first (new system) ──────────────
        cls = widget_engine.get_class(class_name)
        if cls is not None:
            layout = cls.get_layout()
        else:
            # ── Fallback to WIDGET_LAYOUT (transition period) ────
            layout = WIDGET_LAYOUT.get(class_name, {})

        w["render_type"]  = layout.get("render", "kpi")
        w["chart_type"]   = layout.get("chart_type", "")
        w["chart_height"] = layout.get("chart_height", "250px")
        w["tab"]          = layout.get("tab", "produccion")
        w["order"]        = layout.get("order", idx)
        w["downtime_only"]= layout.get("downtime_only", False)

        col_span = layout.get("col_span", 1)
        row_span = layout.get("row_span", 1)
        w["col_span"] = col_span
        w["row_span"] = row_span
        parts = []
        if col_span > 1: parts.append(f"grid-column:span {col_span}")
        if row_span > 1: parts.append(f"grid-row:span {row_span}")
        parts.append(f"order:{w['order']}")
        w["grid_style"] = ";".join(parts)
```

**Agregar recolección de `js_inline`** en la función `index()`:

```python
# Después de _enrich_widgets(widgets_data):
widget_names = [w["widget_name"] for w in widgets_data if isinstance(w, dict)]
widget_inline_js = widget_engine.get_js_inline_blocks(widget_names)

return render_template(
    "dashboard/index.html",
    # ... vars existentes ...
    widget_inline_js=widget_inline_js,   # NUEVO
)
```

### ✅ Checkpoint Fase 3
- Dashboard carga igual que antes (fallback WIDGET_LAYOUT activo)
- `widget_inline_js` llega al template como string vacío (aún no hay js_inline en clases)
- `pytest` verde

---

## FASE 4 — Migrar los 18 widgets
**Archivos:** 18 | **Riesgo:** Bajo por widget (completamente aislados entre sí)

### Patrón de migración

```python
# ANTES:
class KpiTotalProduction(BaseWidget):
    required_columns = ["area_type"]
    default_config   = {}
    render     = "kpi"
    chart_type = ""
    chart_height = "250px"
    # (tab, col_span, order viven en widget_layout.py)
    # (js_inline no existe)

# DESPUÉS:
class KpiTotalProduction(BaseWidget):
    required_columns = ["area_type"]
    default_config   = {}

    # ── Render ──────────────────────────────────────────────
    render       = "kpi"
    chart_type   = ""
    chart_height = "250px"

    # ── Layout ──────────────────────────────────────────────
    tab          = "produccion"
    col_span     = 1
    row_span     = 1
    order        = 7
    downtime_only= False

    # ── JS ──────────────────────────────────────────────────
    js_inline = None   # sin chart, sin handlers especiales

    def process(self) -> WidgetResult:
        # ... sin cambios ...
```

### Tabla completa de migración — los 18 widgets

| Widget | tab | col | row | order | downtime_only | js_inline |
|---|---|---|---|---|---|---|
| `KpiOee` | oee | 1 | 1 | 0 | False | None |
| `KpiAvailability` | oee | 1 | 1 | 1 | False | None |
| `KpiPerformance` | oee | 1 | 1 | 2 | False | None |
| `KpiQuality` | oee | 1 | 1 | 3 | False | None |
| `ProductionTimeChart` | produccion | 4 | 2 | 4 | False | `WidgetChartBuilders['ProductionTimeChart'] = {...}` |
| `ProductDistributionChart` | produccion | 3 | 2 | 5 | False | `WidgetChartBuilders['ProductDistributionChart'] = {...}` |
| `ProductRanking` | produccion | 1 | 2 | 6 | False | None |
| `KpiTotalProduction` | produccion | 1 | 1 | 7 | False | None |
| `KpiTotalWeight` | produccion | 1 | 1 | 8 | False | None |
| `KpiTotalDowntime` | produccion | 1 | 1 | 9 | **True** | None |
| `LineStatusIndicator` | produccion | 1 | 1 | 10 | False | None |
| `AreaDetectionChart` | produccion | 2 | 2 | 11 | False | `WidgetChartBuilders['AreaDetectionChart'] = {...}` |
| `EntryOutputCompareChart` | produccion | 4 | 2 | 12 | False | `WidgetChartBuilders['EntryOutputCompareChart'] = {...}` |
| `ScatterChart` | produccion | 2 | 2 | 13 | **True** | `WidgetChartBuilders['ScatterChart'] = {...}` |
| `DowntimeTable` | produccion | 3 | 2 | 14 | **True** | None |
| `MetricsSummary` | produccion | 2 | 2 | 15 | False | None |
| `EventFeed` | produccion | 4 | 2 | 16 | False | None |
| `LineGroupSummary`* | produccion | 4 | 1 | 17 | False | None |

> *Ajustar si el widget 18 tiene un nombre diferente — verificar contra widget_catalog en DB.

### Detalle del `js_inline` para los 5 widgets chart

Cada bloque mueve el config de `ChartConfigBuilder` al widget correspondiente.
`ChartConfigBuilder` sigue disponible como utilidades compartidas.

#### `ProductionTimeChart` — `js_inline`
```javascript
WidgetChartBuilders['ProductionTimeChart'] = {
    zoomable:   true,
    toggleable: true,   // soporta toggle línea/barra
    buildConfig: function(data, options) {
        try {
            const { resetBtn, isMultiLine, mode } = options;
            // Mueve aquí el código de ChartConfigBuilder.buildLineConfig()
            // Llama a los helpers compartidos:
            //   ChartConfigBuilder._cssVar(...)
            //   ChartConfigBuilder._curveProps(data.curve_type)
            //   ChartConfigBuilder._tooltipDefaults()
            //   ChartConfigBuilder._zoomOptions(resetBtn)
            //   ChartConfigBuilder.buildDowntimeAnnotations(events)
            return { /* config completo de Chart.js */ };
        } catch(e) {
            console.error('[ProductionTimeChart] buildConfig:', e);
            return null;
        }
    },
};
```

#### `ProductDistributionChart` — `js_inline`
```javascript
WidgetChartBuilders['ProductDistributionChart'] = {
    zoomable:   false,
    toggleable: false,
    buildConfig: function(data, options) {
        try {
            // Mueve aquí ChartConfigBuilder.buildPieConfig()
            return { /* Chart.js pie config */ };
        } catch(e) { console.error('[ProductDistributionChart] buildConfig:', e); return null; }
    },
};
```

#### `AreaDetectionChart` — `js_inline`
```javascript
WidgetChartBuilders['AreaDetectionChart'] = {
    zoomable:   true,
    toggleable: false,
    buildConfig: function(data, options) {
        try {
            // Mueve aquí la versión bar de ChartConfigBuilder.buildBarConfig()
            return { /* Chart.js bar config */ };
        } catch(e) { console.error('[AreaDetectionChart] buildConfig:', e); return null; }
    },
};
```

#### `EntryOutputCompareChart` — `js_inline`
```javascript
WidgetChartBuilders['EntryOutputCompareChart'] = {
    zoomable:   true,
    toggleable: false,
    buildConfig: function(data, options) {
        try {
            // Mueve aquí la versión comparison_bar de ChartConfigBuilder.buildBarConfig()
            return { /* Chart.js comparison bar config */ };
        } catch(e) { console.error('[EntryOutputCompareChart] buildConfig:', e); return null; }
    },
};
```

#### `ScatterChart` — `js_inline`
```javascript
WidgetChartBuilders['ScatterChart'] = {
    zoomable:   true,
    toggleable: false,
    buildConfig: function(data, options) {
        try {
            const { resetBtn, isMultiLine } = options;
            // Mueve aquí ChartConfigBuilder.buildScatterConfig()
            return { /* Chart.js scatter config */ };
        } catch(e) { console.error('[ScatterChart] buildConfig:', e); return null; }
    },
};
```

### ✅ Checkpoint Fase 4
- Cada widget migrado: `cls.get_layout()` retorna valores correctos
- `widget_engine.get_js_inline_blocks([...])` retorna los 5 bloques JS
- `_enrich_widgets()` ya NO usa WIDGET_LAYOUT (el fallback nunca se activa)
- Dashboard carga y renderiza igual que antes (JS aún no conectado)
- `pytest` verde

---

## FASE 5 — Template: inyección de `WidgetChartBuilders`
**Archivos:** 1 template | **Riesgo:** Bajo

### `new_app/templates/dashboard/index.html`

Agregar bloque ANTES de los otros `<script>` de dashboard, para que
`WidgetChartBuilders` esté disponible cuando `ChartRenderer` lo necesite:

```html
<!-- ── Widget Chart Builders (auto-injected from widget class js_inline) ── -->
<script>
'use strict';
// Global registry: widget_name → { zoomable, toggleable, buildConfig }
// Populated by each chart widget's js_inline block.
var WidgetChartBuilders = {};

{% if widget_inline_js %}
{{ widget_inline_js | safe }}
{% endif %}
</script>
```

> **Orden de carga crítico:** este `<script>` debe aparecer ANTES de
> `chart-renderer.js` y `dashboard-orchestrator.js` en el HTML.

### ✅ Checkpoint Fase 5
- Browser console: `Object.keys(WidgetChartBuilders)` lista los 5 widgets chart
- Cada builder tiene `zoomable`, `toggleable`, `buildConfig`
- Dashboard carga sin errores JS

---

## FASE 6 — Frontend: conectar `WidgetChartBuilders` al renderer
**Archivos:** 2 JS | **Riesgo:** Medio (es el punto de integración principal)

### 6a. `new_app/static/js/chart-renderer.js` — `render()` actualizado

```javascript
render(chartType, widgetData, chartInstances, isMultiLine, _attempt, mode) {
    if (!widgetData || !widgetData.data) return null;

    const canvasId   = `chart-${widgetData.widget_id}`;
    const widgetName = widgetData.widget_name;   // NUEVO — viene del API result
    const canvas     = document.getElementById(canvasId);

    if (!canvas || canvas.offsetWidth === 0) {
        const attempt = (_attempt || 0) + 1;
        if (attempt <= 10)
            setTimeout(() => this.render(chartType, widgetData, chartInstances,
                                         isMultiLine, attempt, mode), 60);
        return null;
    }

    // Destroy existing
    if (chartInstances[canvasId]) {
        const raw = Alpine?.raw ? Alpine.raw(chartInstances[canvasId])
                                : chartInstances[canvasId];
        raw.destroy();
        delete chartInstances[canvasId];
    }

    // ── Resolve builder ──────────────────────────────────────────
    // 1. Try widget-specific builder (new system)
    const builder = (typeof WidgetChartBuilders !== 'undefined')
                    ? WidgetChartBuilders[widgetName]
                    : null;

    const isZoomable = builder ? builder.zoomable
                               : ['line_chart','bar_chart','comparison_bar','scatter_chart']
                                 .includes(chartType);
    const resetBtn = isZoomable ? this._createZoomToolbar(canvas, chartType, mode) : null;

    let config = null;
    if (builder && typeof builder.buildConfig === 'function') {
        // New path: widget owns its Chart.js config
        config = builder.buildConfig(widgetData.data, {
            resetBtn,
            isMultiLine,
            mode,
            widgetId: widgetData.widget_id,
        });
    } else {
        // Fallback: legacy ChartConfigBuilder switch (transition only)
        config = ChartConfigBuilder.getConfig(chartType, widgetData.data,
                                              resetBtn, isMultiLine, mode);
    }

    if (!config) return null;

    const chart = new Chart(canvas.getContext('2d'), config);
    chartInstances[canvasId] = chart;

    if (resetBtn) {
        resetBtn.onclick = () => { chart.resetZoom(); resetBtn.style.display = 'none'; };
        canvas.addEventListener('dblclick', () => {
            chart.resetZoom(); resetBtn.style.display = 'none';
        });
    }

    return chart;
},

// ── Nuevo método: toggle para widgets que lo soportan ────────────
toggleChartMode(widgetId, mode, widgetData, chartInstances, isMultiLine) {
    const widgetName = widgetData?.widget_name;
    const builder    = WidgetChartBuilders?.[widgetName];
    // Solo re-render si el widget declara que soporta toggle
    if (!builder || !builder.toggleable) return;
    this.render(widgetData.chart_type || 'line_chart', widgetData,
                chartInstances, isMultiLine, 0, mode);
},
```

### 6b. `new_app/static/js/dashboard-orchestrator.js` — `_renderTabCharts()` actualizado

```javascript
_renderTabCharts(ctx, tab) {
    if (!ctx.hasData) return;
    if (!(ctx._renderedTabs instanceof Set)) ctx._renderedTabs = new Set();

    const widgetMeta = ctx._widgetMeta || {};
    const isMulti    = ctx.isMultiLine;
    const instances  = ctx.chartInstances;
    const modes      = ctx.chartModes || {};

    const tabCharts = [];
    Object.keys(ctx.widgetResults).forEach(wid => {
        const wd   = ctx.widgetResults[wid];
        if (!wd || !wd.data) return;
        const meta = widgetMeta[parseInt(wid)] || widgetMeta[wid];
        if (!meta) return;

        const widgetTab = meta.tab || 'produccion';
        if (widgetTab !== tab) return;

        const widgetName = meta.widget_name;
        const chartType  = meta.chart_type || '';

        // ── Check new registry first, fall back to chart_type ──
        const hasBuilder = typeof WidgetChartBuilders !== 'undefined'
                           && !!WidgetChartBuilders[widgetName];
        const isChart    = hasBuilder || !!chartType;
        if (!isChart) return;

        tabCharts.push({ chartType, widgetData: wd, wid });
    });

    if (tabCharts.length === 0) return;

    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            tabCharts.forEach(cw => {
                const mode = modes[cw.wid] || 'line';
                ChartRenderer.render(cw.chartType, cw.widgetData,
                                     instances, isMulti, 0, mode);
            });
        });
    });

    ctx._renderedTabs.add(tab);
},
```

### ✅ Checkpoint Fase 6
- Todos los charts renderizan usando `WidgetChartBuilders` (verificar en consola)
- `toggleChartMode` en `ProductionTimeChart` funciona (línea/barra)
- `updateCurveType` sigue funcionando (opera sobre instancias Chart.js directamente)
- `updateDowntimeAnnotations` sigue funcionando (ídem)
- Modo multi-línea correcto (`downtime_only = True` en `ScatterChart`, etc.)
- `pytest` verde
- Ningún widget perdió funcionalidad visual

---

## FASE 7 — Limpieza: eliminar código muerto
**Archivos:** 3 | **Riesgo:** Bajo

### 7a. Eliminar `widget_layout.py`

```bash
# Verificar primero que no hay más importaciones:
grep -r "WIDGET_LAYOUT\|widget_layout" new_app/ --include="*.py"
# Esperado: cero resultados (el fallback de _enrich_widgets ya no se activa)

# Eliminar:
rm new_app/config/widget_layout.py
```

### 7b. Remover import y fallback de `routes/dashboard.py`

```python
# ELIMINAR estas líneas:
from new_app.config.widget_layout import WIDGET_LAYOUT, GRID_COLUMNS, SHOW_OEE_TAB

# REEMPLAZAR por:
from new_app.services.widgets.engine import widget_engine
GRID_COLUMNS = 4
SHOW_OEE_TAB = False  # o leer desde settings directamente
```

Eliminar el bloque de fallback en `_enrich_widgets()`:
```python
# ELIMINAR el bloque else con WIDGET_LAYOUT.get(class_name, {}):
# Si cls es None, loggear error y usar defaults vacíos
if cls is None:
    logger.error("[Dashboard] Widget class not found: %s", class_name)
    layout = {}
```

### 7c. Limpiar `ChartConfigBuilder.getConfig()` (opcional, post-confirmación)

Una vez confirmado en producción que el `else` (fallback a `ChartConfigBuilder.getConfig()`)
en `ChartRenderer.render()` nunca se ejecuta, se puede eliminar el switch de `getConfig()`:

```javascript
// En chart-config.js, marcar como deprecated:
getConfig(chartType, data, resetBtn, isMultiLine, mode) {
    // DEPRECATED: use WidgetChartBuilders instead.
    // This fallback remains for external widgets or direct calls.
    switch (chartType) { ... }
},
```

> No eliminar `ChartConfigBuilder` completo — sus helpers compartidos
> (`_tooltipDefaults`, `_zoomOptions`, `_cssVar`, `buildDowntimeAnnotations`,
> `_curveProps`) son usados por los `js_inline` de los widgets. Solo el
> método `getConfig()` se convierte en dead code.

### ✅ Checkpoint Fase 7 — Estado final
- `grep -r "WIDGET_LAYOUT" .` → cero resultados
- Dashboard funciona idéntico al pre-refactor visualmente
- Agregar un widget nuevo toca 1 archivo + 1 SQL (verificar con caso de prueba real)
- `pytest` verde

---

## Resumen ejecutivo

| Fase | Qué | Archivos | Riesgo | Desplegable solo |
|---|---|---|---|---|
| 1 | Nuevos atributos en `BaseWidget` | 1 | Muy bajo | ✅ |
| 2 | `get_class()` + `get_js_inline_blocks()` en WidgetEngine | 1 | Muy bajo | ✅ |
| 3 | `_enrich_widgets()` dual (clase + fallback) + recolección js_inline | 1 | Bajo | ✅ |
| 4 | Migrar 18 widgets (layout attrs + js_inline en 5 chart) | 18 | Bajo c/u | ✅ de a uno |
| 5 | Inyección `WidgetChartBuilders` en template | 1 | Bajo | ✅ |
| 6 | `ChartRenderer` y `_renderTabCharts` usan registry | 2 JS | Medio | ⚠️ en rama |
| 7 | Eliminar `widget_layout.py` + fallbacks | 3 | Bajo | ✅ |

**Estimación:** 10–14 horas efectivas en 2–3 sesiones.

**Orden de sesiones:**
- **Sesión 1:** Fases 1 + 2 + 3 — solo Python e infraestructura
- **Sesión 2:** Fase 4 — migración de los 18 widgets
- **Sesión 3:** Fases 5 + 6 + 7 — conexión frontend + cleanup

---

## Anatomía del widget post-refactor

```python
# new_app/services/widgets/types/mi_nuevo_widget.py
"""MiNuevoWidget — descripción."""
from __future__ import annotations
from new_app.services.widgets.base import BaseWidget, WidgetResult

class MiNuevoWidget(BaseWidget):

    # ── Datos ────────────────────────────────────────────────────
    required_columns = ["detected_at", "product_id"]
    default_config   = {"top_n": 10}

    # ── Render ───────────────────────────────────────────────────
    render       = "kpi"     # kpi | kpi_oee | chart | table |
                              # ranking | indicator | summary | feed
    chart_type   = ""        # solo si render = "chart"
    chart_height = "250px"

    # ── Layout ───────────────────────────────────────────────────
    tab          = "produccion"   # "produccion" | "oee"
    col_span     = 1              # 1–4
    row_span     = 1              # 1–2
    order        = 20             # siguiente disponible
    downtime_only= False

    # ── JS: None para no-chart, builder para chart ───────────────
    js_inline = None
    # Para widget chart:
    # js_inline = """
    # WidgetChartBuilders['MiNuevoWidget'] = {
    #     zoomable: false, toggleable: false,
    #     buildConfig: function(data, options) {
    #         return { type: 'bar', data: {...}, options: {...} };
    #     },
    # };
    # """

    def process(self) -> WidgetResult:
        if self.df.empty:
            return self._empty(self.render)

        data = {"value": len(self.df), "label": "Mi métrica", "unit": "uds"}
        return self._result(widget_type=self.render, data=data,
                            category="produccion")
```

```sql
-- DB: una sola línea
INSERT INTO widget_catalog (widget_name, display_name, description, is_active)
VALUES ('MiNuevoWidget', 'Mi Nuevo Widget', 'Descripción', 1);
-- Agregar widget_id al layout_config del dashboard_template
```

**Eso es todo. Cero archivos de código adicionales.**

---

## Diferencia vs plan de filtros

| Aspecto | Filtros | Widgets |
|---|---|---|
| Estado de configuración | `pydantic_type`, `js_behavior` (dict) | layout attrs planos (`tab`, `col_span`, etc.) |
| JS inline | Métodos Alpine (handlers de UI) | Registros en `WidgetChartBuilders` (Chart.js config) |
| Dispatcher JS actual | `_buildRequestBody` (loop) | `ChartConfigBuilder.getConfig()` (switch) |
| Dispatcher JS nuevo | Loop genérico sobre `filterStates` | `WidgetChartBuilders[name].buildConfig()` |
| Intermediario eliminado | `DropdownFilter`, `ToggleFilter`, etc. | `widget_layout.py` |
| Fallback en transición | `params` getter proxy en Alpine | Bloque `else` en `ChartRenderer.render()` |