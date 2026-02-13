"""
Filter Registry Configuration.

Maps filter class names (stored in ``filter.filter_name``) to their
runtime metadata.  This is the single file to edit when adding a new
filter type — no switches, no factory dicts, no long conditionals.

Keys:
  class_name → str : must match filter.filter_name in the tenant DB.

Values: dict with:
  filter_type    → str        : "daterange" | "dropdown" | "multiselect" |
                                "text" | "number" | "toggle"
  param_name     → str        : HTTP parameter name sent from the frontend.
  options_source → str | None : cache key for dynamic options
                                (e.g. "production_lines", "shifts", "products",
                                 "areas").  None for static filters.
  default_value  → Any        : default if user provides nothing.
  placeholder    → str | None : input placeholder text.
  required       → bool       : whether the filter must have a value.
  depends_on     → str | None : param_name of the parent filter (cascade).
  ui_config      → dict       : extra frontend rendering hints.

To add a new filter:
  1. Create a class in new_app/services/filters/types/
  2. Add an entry here with the class name as key.
  3. INSERT a row in ``filter`` with filter_name = class_name.
  Done.
"""

FILTER_REGISTRY: dict[str, dict] = {
    "DateRangeFilter": {
        "filter_type": "daterange",
        "param_name": "daterange",
        "options_source": None,
        "default_value": None,
        "placeholder": None,
        "required": True,
        "depends_on": None,
        "ui_config": {
            "show_time": True,
            "default_start_time": "00:00",
            "default_end_time": "23:59",
        },
    },
    "ProductionLineFilter": {
        "filter_type": "dropdown",
        "param_name": "line_id",
        "options_source": "production_lines",
        "default_value": None,
        "placeholder": "Seleccionar línea",
        "required": True,
        "depends_on": None,
        "ui_config": {"supports_groups": True},
    },
    "ShiftFilter": {
        "filter_type": "dropdown",
        "param_name": "shift_id",
        "options_source": "shifts",
        "default_value": None,
        "placeholder": "Todos los turnos",
        "required": False,
        "depends_on": None,
        "ui_config": {},
    },
    "AreaFilter": {
        "filter_type": "multiselect",
        "param_name": "area_ids",
        "options_source": "areas",
        "default_value": [],
        "placeholder": "Todas las áreas",
        "required": False,
        "depends_on": "line_id",
        "ui_config": {},
    },
    "ProductFilter": {
        "filter_type": "multiselect",
        "param_name": "product_ids",
        "options_source": "products",
        "default_value": [],
        "placeholder": "Todos los productos",
        "required": False,
        "depends_on": None,
        "ui_config": {},
    },
    "IntervalFilter": {
        "filter_type": "dropdown",
        "param_name": "interval",
        "options_source": None,
        "default_value": "hour",
        "placeholder": None,
        "required": True,
        "depends_on": None,
        "ui_config": {
            "static_options": [
                {"value": "hour", "label": "Por hora"},
                {"value": "day", "label": "Por día"},
                {"value": "week", "label": "Por semana"},
                {"value": "month", "label": "Por mes"},
            ]
        },
    },
    "CurveTypeFilter": {
        "filter_type": "dropdown",
        "param_name": "curve_type",
        "options_source": None,
        "default_value": "smooth",
        "placeholder": None,
        "required": False,
        "depends_on": None,
        "ui_config": {
            "static_options": [
                {"value": "smooth", "label": "Suavizado"},
                {"value": "linear", "label": "Lineal"},
                {"value": "stepped", "label": "Escalonado"},
                {"value": "stacked", "label": "Apilado"},
            ]
        },
    },
    "DowntimeThresholdFilter": {
        "filter_type": "number",
        "param_name": "downtime_threshold",
        "options_source": None,
        "default_value": 300,
        "placeholder": "Segundos",
        "required": False,
        "depends_on": "line_id",
        "ui_config": {"min": 0, "step": 10, "unit": "s"},
    },
    "ShowDowntimeFilter": {
        "filter_type": "toggle",
        "param_name": "show_downtime",
        "options_source": None,
        "default_value": True,
        "placeholder": None,
        "required": False,
        "depends_on": None,
        "ui_config": {"label": "Mostrar paradas"},
    },
    "SearchFilter": {
        "filter_type": "text",
        "param_name": "search",
        "options_source": None,
        "default_value": "",
        "placeholder": "Buscar…",
        "required": False,
        "depends_on": None,
        "ui_config": {"debounce_ms": 300},
    },
}
