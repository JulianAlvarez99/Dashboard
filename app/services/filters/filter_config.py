"""
Filter Configuration Registry
Defines filter types and their configuration by filter_id
This is the source of truth for how each filter behaves in the UI
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum


class FilterType(Enum):
    """Available filter types for the UI"""
    DROPDOWN = "dropdown"           # Single select dropdown
    MULTISELECT = "multiselect"     # Multiple select with checkboxes
    DATERANGE = "daterange"         # Date range picker (start/end)
    TEXT = "text"                   # Text input for search
    NUMBER = "number"               # Number input
    TOGGLE = "toggle"               # Boolean toggle/checkbox
    SELECT_BUTTONS = "select_buttons"  # Button group for quick selection


class OptionsSource(Enum):
    """Sources for dynamic options loaded from cache/API"""
    PRODUCTION_LINE = "production_line"
    PRODUCT = "product"
    SHIFT = "shift"
    AREA = "area"
    STATIC = "static"  # Options defined in config, not from DB


@dataclass
class FilterConfig:
    """Configuration for a single filter"""
    filter_type: FilterType
    options_source: Optional[OptionsSource] = None
    static_options: Optional[List[Dict[str, Any]]] = None  # For STATIC source
    default_value: Any = None
    depends_on: Optional[int] = None  # filter_id that this filter depends on
    param_name: str = ""  # The parameter name to send to API
    placeholder: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "filter_type": self.filter_type.value,
            "options_source": self.options_source.value if self.options_source else None,
            "static_options": self.static_options,
            "default_value": self.default_value,
            "depends_on": self.depends_on,
            "param_name": self.param_name,
            "placeholder": self.placeholder
        }


# =============================================================================
# FILTER REGISTRY
# Maps filter_id from database to its UI configuration
# =============================================================================

FILTER_REGISTRY: Dict[int, FilterConfig] = {
    # 1: Rango de fechas
    1: FilterConfig(
        filter_type=FilterType.DATERANGE,
        param_name="date_range",
        default_value={"days_back": 7}  # Last 7 days by default
    ),
    
    # 2: Linea de produccion
    2: FilterConfig(
        filter_type=FilterType.DROPDOWN,
        options_source=OptionsSource.PRODUCTION_LINE,
        param_name="line_id",
        placeholder="Todas las líneas"
    ),
    
    # 3: Productos
    3: FilterConfig(
        filter_type=FilterType.MULTISELECT,
        options_source=OptionsSource.PRODUCT,
        param_name="product_ids",
        placeholder="Todos los productos"
    ),
    
    # 4: Turno
    4: FilterConfig(
        filter_type=FilterType.DROPDOWN,
        options_source=OptionsSource.SHIFT,
        param_name="shift_id",
        placeholder="Todos los turnos"
    ),
    
    # 5: Intervalo de agregacion
    5: FilterConfig(
        filter_type=FilterType.DROPDOWN,
        options_source=OptionsSource.STATIC,
        static_options=[
            {"value": "minute", "label": "Por Minuto"},
            {"value": "15min", "label": "Cada 15 Minutos"},
            {"value": "hour", "label": "Por Hora"},
            {"value": "day", "label": "Por Día"},
            {"value": "week", "label": "Por Semana"},
            {"value": "month", "label": "Por Mes"}
        ],
        param_name="interval",
        default_value="hour"
    ),
    
    # 6: Umbral de parada (en segundos)
    6: FilterConfig(
        filter_type=FilterType.NUMBER,
        param_name="downtime_threshold",
        default_value=300,  # 5 minutes = 300 seconds
        placeholder="Ej: 300 = 5 min"
    ),
    
    # 7: Mostrar paradas
    7: FilterConfig(
        filter_type=FilterType.TOGGLE,
        param_name="show_downtime",
        default_value=True
    ),
    
    # 8: Busqueda
    8: FilterConfig(
        filter_type=FilterType.TEXT,
        param_name="search",
        placeholder="Buscar por código o nombre..."
    ),
    
    # 9: Tipo de curva
    9: FilterConfig(
        filter_type=FilterType.SELECT_BUTTONS,
        options_source=OptionsSource.STATIC,
        static_options=[
            {"value": "stepped", "label": "Escalonada", "icon": "stairs"},
            {"value": "smooth", "label": "Suave", "icon": "wave"},
            {"value": "linear", "label": "Recta", "icon": "line"},
            {"value": "stacked", "label": "Apilada", "icon": "layers"}
        ],
        param_name="curve_type",
        default_value="smooth"
    )
}


def get_filter_config(filter_id: int) -> Optional[FilterConfig]:
    """Get configuration for a specific filter by ID"""
    return FILTER_REGISTRY.get(filter_id)


def get_all_filter_configs() -> Dict[int, FilterConfig]:
    """Get all filter configurations"""
    return FILTER_REGISTRY.copy()
