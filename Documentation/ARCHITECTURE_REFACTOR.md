# Arquitectura y Refactorización — Camet Analytics

Documenta los patrones arquitectónicos, decisiones de diseño y la estructura modular del sistema.

**Última actualización:** 13 Febrero 2026

---

## 1. Arquitectura Dual-Server

### ¿Por qué dos servidores?

| Decisión | Justificación |
|----------|---------------|
| **FastAPI para API** | Async nativo, rendimiento en I/O-bound (DB queries), OpenAPI auto-docs, Pydantic validation |
| **Flask para Frontend** | Jinja2 SSR maduro, system de sesiones built-in, integración simple con templates |
| **Comunicación interna** | Flask hace proxy a FastAPI via `httpx` cuando necesita datos |
| **Mismo codebase** | Comparten `app/core/`, `app/models/`, `app/services/` |

### Lifespan de FastAPI

```python
# app/main.py
@asynccontextmanager
async def lifespan(app):
    await metadata_cache.load_all()   # Carga cache al startup
    yield
    # Cleanup (si fuera necesario)
```

El cache se carga UNA vez al arrancar. Todos los requests posteriores usan datos in-memory. Si se inicia una nueva sesion, o la sesion se expira, debe volver a traer el caché

---

## 2. Capas de la Aplicación

```
┌──────────────────────────────────────────────────┐
│                   PRESENTATION                     │
│  Templates (Jinja2) │ API Endpoints (FastAPI)      │
│  dashboard-app.js   │ chart-renderer.js            │
├──────────────────────────────────────────────────┤
│                    SERVICE                         │
│  DashboardDataService (orquestador)                │
│  FilterResolver │ LayoutService │ DataAggregator   │
├──────────────────────────────────────────────────┤
│                   PROCESSORS                       │
│  kpi.py │ charts/ │ tables.py │ ranking/           │
│  downtime_calculator.py │ helpers.py               │
├──────────────────────────────────────────────────┤
│                 DATA ACCESS                        │
│  MetadataCache │ DatabaseManager │ SQLAlchemy       │
├──────────────────────────────────────────────────┤
│                   DATABASE                         │
│  camet_global │ db_client_{tenant}                 │
└──────────────────────────────────────────────────┘
```

### Flujo de dependencias

```
Endpoints → Services → Processors → Cache (lectura)
                    → Aggregators → DB (lectura)
```

Los procesadores NUNCA acceden a la DB directamente. Reciben `DashboardData` (DataFrames enriquecidos) y el cache para metadatos estáticos.

---

## 3. Patrones de Diseño Aplicados

### 3.1 Factory Pattern

**FilterFactory** (`app/services/filters/factory.py`):
```python
_filter_map = {
    "daterange": DateRangeFilter,
    "dropdown": DropdownFilter,
    "multiselect": MultiselectFilter,
    "text": TextFilter,
    "number": NumberFilter,
    "toggle": ToggleFilter,
    "checkbox": ToggleFilter,   # Alias
}
```
Permite agregar nuevos tipos de filtro registrando una clase en el mapa, sin modificar el resolver.

**PROCESSOR_MAP** (`app/services/processors/__init__.py`):
```python
PROCESSOR_MAP = {
    "kpi_total_production": process_kpi_production,
    "line_chart": process_line_chart,
    # ... 16 tipos
}
```
Nuevos widgets se agregan registrando su función procesadora en el mapa.

**ChartRenderer._configBuilders** (`chart-renderer.js`):
```javascript
_configBuilders: {
    'line_chart': 'buildLineConfig',
    'bar_chart': 'buildBarConfig',
    // ...
}
```

### 3.2 Singleton

- `MetadataCache`: `__new__` retorna la misma instancia
- `ChartRenderer`: Objeto literal JS global
- `DatabaseManager`: Instancia global `db_manager`
- `Settings`: Cached via `@lru_cache` en `get_settings()`

### 3.3 Strategy

Los tipos de filtro (`BaseFilter` → subclases) implementan `get_options()` de forma diferente según su tipo. El `DropdownFilter` carga opciones del cache; el `DateRangeFilter` genera rangos estáticos.

### 3.4 Facade

`FilterResolver` es una fachada que orquesta `FilterFactory`, `MetadataCache` y los filtros individuales para resolver configuraciones completas con opciones.

`DashboardDataService` es una fachada sobre `DataAggregator`, `DowntimeCalculator` y los procesadores.

### 3.5 Data Transfer Object (DTO)

- `FilterParams`: Dataclass que encapsula todos los parámetros de filtrado
- `DashboardData`: Container para DataFrames enriquecidos
- `FilterConfig`: Config de un filtro
- `WidgetConfig`: Config de un widget

---

## 4. Decisiones de Enriquecimiento Application-Side

### ¿Por qué joins en Python y no en SQL?

| Factor | SQL JOINs | Python + Cache |
|--------|------------|----------------|
| **Tablas dinámicas** | No se puede hacer JOIN a una tabla cuyo nombre no se conoce en compile-time | El nombre se construye en runtime |
| **N tablas por línea** | Requeriría UNION ALL dinámicos | Iteramos y concatenamos DataFrames |
| **Carga de hosting** | JOINs pesados en shared hosting → lento | Queries simples + enrich in-memory |
| **Flexibilidad** | Modificar JOINs requiere cambiar SQL | Agregar campos de enrich es trivial |

### Flujo de enriquecimiento

```
detection_line_X (raw)
  ↓ fetch
DataFrame[detection_id, detected_at, area_id, product_id, line_id]
  ↓ enrich_with_metadata()
  + area_name, area_type, product_name, product_code, product_weight, product_color
  ↓ enrich_with_line_metadata()
  + line_name, line_code
  ↓
DataFrame enriquecido → pasa a TODOS los procesadores
```

---

## 5. Separación Frontend-Backend

### SSR con Hidratación Reactiva

Flask renderiza el HTML inicial con datos de configuración (filtros, widgets, layout) embedded como JSON en atributos `x-data`. Alpine.js hidrata esos datos para reactividad client-side.

```html
<!-- index.html (simplificado) -->
<div x-data="dashboardApp({{ filter_configs|tojson }}, {{ widget_configs|tojson }}, '{{ api_base_url }}')">
  <!-- El HTML renderizado por Flask contiene la estructura -->
  <!-- Alpine.js maneja la interactividad -->
  <!-- Chart.js renderiza los gráficos una vez llegan los datos -->
</div>
```

### Zero Build Step

Todo el frontend se carga via CDN:
- Alpine.js, Chart.js, plugins, Hammer.js: `<script>` tags
- Tailwind CSS: CDN `<script>` con configuración inline
- **No hay npm, webpack, vite ni ningún bundler**

Esto simplifica el deploy pero impide tree-shaking y compilación customizada.

---

## 6. Gestión de Conexiones de Base de Datos

### NullPool

Se usa `NullPool` (sin connection pooling) para compatibilidad con hosting compartido (cPanel) que limita conexiones simultáneas.

```python
create_async_engine(
    url,
    poolclass=NullPool,          # Sin pool
    connect_args={"charset": "utf8mb4"}
)
```

**Trade-off**: Cada request abre y cierra una conexión. Mayor latencia por request, pero no se agotan las conexiones.

### Context Managers

```python
# Async (FastAPI)
async with db_manager.get_tenant_session() as session:
    result = await session.execute(text(...))

# Sync (Flask)
with db_manager.get_global_session_sync() as session:
    user = authenticate_user(session, ...)
```

Todos los context managers hacen commit automático o rollback en excepción.

---

## 7. Configuración y Settings

### Pydantic Settings v2

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore"
    )
    # 30+ variables de configuración
```

Todas las settings se cargan desde `.env` con validación de tipos. El `@lru_cache` en `get_settings()` asegura que solo se parsee una vez.

### Properties calculados

```python
@property
def global_db_url(self) -> str:       # mysql+aiomysql://...
def global_db_url_sync(self) -> str:   # mysql+pymysql://...
def tenant_db_url(self) -> str:        # mysql+aiomysql://...
def tenant_db_url_sync(self) -> str:   # mysql+pymysql://...
```

---

_Documento de arquitectura actualizado. Para detalles de cálculos, ver [Documentation.md](Documentation.md)._
