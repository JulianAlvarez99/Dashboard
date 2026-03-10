# Guía de Agente — Cómo Agregar un Filtro o un Widget (dashboard_saas)

> **Propósito:** Esta guía está diseñada para que un agente de IA pueda implementar nuevos filtros y widgets dentro de la arquitectura modular y dinámica del sistema `dashboard_saas`.
> El usuario indica qué quiere agregar y el agente ejecuta los pasos aquí detallados usando la infraestructura orientada a objetos (BaseFilter/BaseWidget).

---

## ARQUITECTURA GENERAL

- El sistema está impulsado por **Auto-descubrimiento estricto**. Todo componente nuevo debe agregarse sin tocar las rutas (FastAPI/Flask) ni el estado principal en `dashboard-app.js`.
- Los motores Singletons (`FilterEngine`, `WidgetEngine`) se encargan de orquestar.
- Existe un enlace automático por convención de nombres entre Backend y Frontend:
  *Clase Python:* `DateRangeFilter` → *Archivo .py:* `date_range_filter.py` → *Archivo .js autoinyectado:* `date_range_filter.js`.

---

## PLAN: AGREGAR UN FILTRO NUEVO

### Paso 1 — Crear la clase del filtro (Backend - Python)

**Archivo:** `dashboard_saas/services/filters/types/{nombre_clase_snake}.py`

Todos los filtros deben heredar de `BaseFilter` estipulado en `dashboard_saas/services/filters/base.py`.

**Plantilla Base:**

```python
"""DateRangeFilter — Selector de rango de fechas."""
from typing import Any, Dict, List, Optional, Tuple

from dashboard_saas.services.filters.base import BaseFilter, FilterOption


class DateRangeFilter(BaseFilter):
    """
    Filtro para inyectar cláusulas de rango de fechas.
    """

    # ── Atributos obligatorios ─────────────────────────────────────
    filter_type = "date_range"    # Tipo para render UI
    param_name = "daterange"      # Key en payload y window.FilterHandlers
    required = True
    placeholder = "Seleccione fechas"
    default_value = None
    ui_config = {}                # Dict libre para pasar opciones extra al frontend

    # ── Métodos para la Vista ──────────────────────────────────────
    def get_options(self) -> List[FilterOption]:
        """
        Obligatorio implementarlo si filter_type es 'dropdown' o 'multiselect'.
        Para otros (date_range, toggle, input) se puede retornar [].
        """
        return []

    # ── Métodos de Validación ──────────────────────────────────────
    def validate(self, value: Any) -> bool:
        """
        Lógica de validación. Retornar True si es válido.
        Se ejecuta dinámicamente en FilterEngine antes de tocar la DB.
        """
        if not value:
            return not self.required
        return True

    # ── Resolución Dinámica de Tablas ──────────────────────────────
    def get_target_tables(self, value: Any) -> List[str]:
        """
        ¡PRECAUCIÓN! Sobrescribir este método SÓLO si este filtro es el responsable
        de dictar A QUÉ TABLA FÍSICA conectarse (Ej: Filtro de Línea de Producción).
        Para filtros convencionales que sólo aportan un WHERE, retornar `[]` o no
        sobrescribir el método base.
        """
        return []

    # ── Construcción SQL ───────────────────────────────────────────
    def to_sql_clause(self, value: Any) -> Optional[Tuple[str, Dict]]:
        """
        Dado el valor validado, generar la cláusula SQL y su diccionario de params.
        """
        if not value:
            return None
        
        # Suponiendo que value = {"start": "2024...", "end": "2024..."}
        return "detected_at >= :start_dt AND detected_at <= :end_dt", {
            "start_dt": value["start"], 
            "end_dt": value["end"]
        }
```

### Paso 2 — Crear el Controlador de Interfaz (Frontend - JS)

**Archivo:** `dashboard_saas/static/js/filters/{nombre_clase_snake}.js`

> ⚡ **Auto-inyección:** La clase padre `BaseFilter` de Python deduce el nombre del archivo JavaScript a partir de tu clase (`DateRangeFilter` → `date_range_filter.js`). La plantilla `index.html` ya incluye dinámicamente la etiqueta `<script src="...">` para este archivo si lo encuentra.

Se debe registrar un manejador en el objeto global `window.FilterHandlers` bajo la clave que coincida exacto con su `param_name`.

**Plantilla JS:**

```javascript
'use strict';

window.FilterHandlers = window.FilterHandlers || {};

// 'daterange' debe COINCIDIR con la variable param_name de la clase Python
window.FilterHandlers['daterange'] = {
    /**
     * @param {Object} app - La instancia actual de Alpine.js (dashboardApp)
     *                       Puedes acceder a app.filterStates, app.loading, app.lastQueryInfo
     * @param {Any} value - El nuevo valor introducido en el input
     * @param {Object} config - Las variables serializadas desde el backend (ui_config, required, etc)
     */
    onChange: function(app, value, config) {
        console.log(`[${config.param_name}] Valor actualizado a:`, value);
        
        // Ejemplo de lógica que puede tener un filtro en particular:
        // if (value && value.start && value.end) {
        //     // Disparar carga automáticamente en lugar de esperar click al botón "Aplicar"
        //     app.applyFilters();
        // }
    }
};
```

### Paso 3 — Registrar en la Base de Datos

El sistema no autodescubre archivos físicos del disco duro. Descubre archivos basándose en una "tabla catálogo" oficial.

Debe existir este registro para que sea funcional (Tenant DB):

```sql
INSERT INTO filter (filter_name, additional_filter, is_active)
VALUES ('DateRangeFilter', NULL, 1);
```
> `filter_name` **DEBE** coincidir con el nombre de la clase Python de forma Case Sensitive.
Luego de ingresado el registro en la DB, todo el flujo desde validación, inyección SQL, carga en Jinja2 e inyección de JS funcionará automáticamente.

---

## FLUJO DE DATOS (Recordatorio SaaS Architecture)

1. El usuario interactúa con la UI (ej. elige fecha). Alpine.js actualiza `this.filterStates['daterange']`.
2. Se ejecuta `window.FilterHandlers['daterange'].onChange()` si fue declarado el JS.
3. El usuario pulsa Aplicar (o se llama vía JS): Se dispara payload asíncrono hacia FastAPI `POST /api/v1/dashboard/apply-filters`.
4. `FilterEngine.validate_request()` recorre todos los filtros activos pidiendo `.validate()`.
5. `FilterEngine.get_target_tables()` suma todas las tablas devueltas (normalmente sólo las aporta el Filtro de Línea, con `[]` en el resto).
6. `FilterEngine.collect_sql_clauses()` junta la string de texto de los `WHERE`.
7. `QueryBuilder` ensambla y ejecuta contra DB de forma agnóstica a los requerimientos del filtro.

---

## PLAN: AGREGAR UN WIDGET NUEVO

(Bajo el diseño actual del proyecto, se repite un principio muy análogo al de los filtros. Se delega toda lógica a la clase particular en Python y se evita inyectar condicionales directos en el motor de API).

### Paso 1 — Crear la Clase
**Archivo:** `dashboard_saas/services/widgets/types/{nombre_clase_snake}.py`

Los widgets heredan de `BaseWidget` (lógica definida en fase de widgets).

### Paso 2 — Registrar en DB Global Catálogo

```sql
INSERT INTO widget_catalog (widget_name, display_name, description, is_active)
VALUES ('KpiRejectedRate', 'Tasa de Rechazo', 'Métrica de fallos', 1);
```
> `widget_name` **DEBE** coincidir con el nombre de la clase Python. 

✅ Recuerda en ambos casos: Cumplir estrictamente el contrato (Heredar clase Abstracta, implementar métodos Base y dejar que los Singletons Orquestadores hagan su trabajo). No añadir IF explícitos de "nombres de filtros" dentro del código principal (main, routers, API endpoints).
