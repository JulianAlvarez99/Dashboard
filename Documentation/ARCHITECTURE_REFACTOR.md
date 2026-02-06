# Dashboard Architecture - SRP & DRY Implementation

## Overview

This document explains the refactored architecture for filters and widgets, implementing **Single Responsibility Principle (SRP)** and **Don't Repeat Yourself (DRY)** principles for maximum scalability and maintainability.

## Architecture Principles

### Single Responsibility Principle (SRP)
- Each filter type has its own class with a single responsibility
- Each widget type has its own class with a single responsibility
- Shared logic is extracted into dedicated utility classes
- Each class focuses on one specific aspect of the system

### Don't Repeat Yourself (DRY)
- Common data fetching logic centralized in `DataAggregator`
- Shared filter option loading logic in base classes
- Factory pattern eliminates repetitive instantiation code
- Base classes provide common functionality

## Directory Structure

```
app/services/
├── filters/
│   ├── __init__.py
│   ├── base.py                  # Base classes for all filters
│   ├── factory.py               # FilterFactory for creating filter instances
│   ├── filter_config.py         # Original filter configuration (kept for compatibility)
│   ├── filter_resolver.py       # Main entry point, now uses factory
│   └── types/                   # Specific filter implementations
│       ├── __init__.py
│       ├── daterange.py         # DateRangeFilter
│       ├── dropdown.py          # DropdownFilter
│       ├── multiselect.py       # MultiselectFilter
│       ├── text.py              # TextFilter
│       ├── number.py            # NumberFilter
│       └── toggle.py            # ToggleFilter
│
└── widgets/
    ├── __init__.py
    ├── base.py                  # Base classes for all widgets
    ├── factory.py               # WidgetFactory for creating widget instances
    ├── aggregators.py           # DataAggregator for shared data fetching
    ├── widget_renderer.py       # Main entry point, now uses factory
    └── types/                   # Specific widget implementations
        ├── __init__.py
        ├── kpi_production.py    # KPIProductionWidget
        ├── kpi_weight.py        # KPIWeightWidget
        ├── kpi_oee.py           # KPIOEEWidget
        ├── kpi_downtime.py      # KPIDowntimeWidget
        ├── line_chart.py        # LineChartWidget
        ├── bar_chart.py         # BarChartWidget
        ├── pie_chart.py         # PieChartWidget
        ├── comparison_bar.py    # ComparisonBarWidget
        └── downtime_table.py    # DowntimeTableWidget
```

## Filter System

### Base Classes

#### `BaseFilter` (Abstract)
- Defines interface for all filter types
- Methods: `get_options()`, `validate_value()`, `get_default_value()`, `to_dict()`
- Each filter type inherits and implements specific logic

#### `OptionsFilter` (Abstract)
- Base for filters with options (dropdown, multiselect)
- Implements option caching
- Subclasses implement `_load_options()`

#### `InputFilter` (Abstract)
- Base for input-based filters (text, number, date)
- No options to load, just validation

### Specific Filter Types

#### DateRangeFilter
- **Responsibility**: Handle date/time range selection
- **Features**: 
  - Date validation (start <= end)
  - Default ranges (e.g., last 7 days)
  - Convert to datetime objects
- **File**: `app/services/filters/types/daterange.py`

#### DropdownFilter
- **Responsibility**: Single selection from options
- **Features**:
  - Load options from cache (production lines, areas, products, shifts)
  - Support parent dependencies (cascading)
  - Option validation
- **File**: `app/services/filters/types/dropdown.py`

#### MultiselectFilter
- **Responsibility**: Multiple selection from options
- **Features**:
  - Inherits option loading from DropdownFilter
  - Validates list of values
  - Default value as list
- **File**: `app/services/filters/types/multiselect.py`

#### TextFilter
- **Responsibility**: Free text input
- **Features**:
  - Min/max length validation
  - Configurable constraints
- **File**: `app/services/filters/types/text.py`

#### NumberFilter
- **Responsibility**: Numeric input
- **Features**:
  - Integer/float support
  - Min/max validation
  - Type coercion
- **File**: `app/services/filters/types/number.py`

#### ToggleFilter
- **Responsibility**: Boolean on/off switch
- **Features**:
  - Boolean validation
  - Default value handling
- **File**: `app/services/filters/types/toggle.py`

### FilterFactory

**File**: `app/services/filters/factory.py`

The factory creates filter instances based on type:

```python
from app.services.filters.factory import FilterFactory
from app.services.filters.base import FilterConfig

config = FilterConfig(
    filter_id=1,
    filter_name="Línea de Producción",
    param_name="line_id",
    filter_type="dropdown",
    options_source="production_line"
)

filter_instance = FilterFactory.create(config)
options = filter_instance.get_options()
```

**Features**:
- Type mapping (type string → class)
- Keyword detection from names
- Extensible via `register_filter_type()`

### FilterResolver (Updated)

**File**: `app/services/filters/filter_resolver.py`

Now delegates to FilterFactory:

```python
from app.services.filters.filter_resolver import FilterResolver

# Resolve single filter
filter_dict = FilterResolver.resolve_filter(filter_id=1, parent_values={"line_id": 1})

# Resolve multiple filters
filters = FilterResolver.resolve_filters([1, 2, 3])
```

## Widget System

### Base Classes

#### `BaseWidget` (Abstract)
- Defines interface for all widget types
- Methods: `render()`, `_create_widget_data()`, `_create_empty_response()`
- Each widget type inherits and implements specific logic

#### `KPIWidget` (Abstract)
- Base for KPI widgets
- Methods: `_calculate_value()`, `_calculate_trend()`, `_get_unit()`
- Handles trend calculation

#### `ChartWidget` (Abstract)
- Base for chart widgets
- Methods: `_fetch_data()`, `_process_chart_data()`
- Returns labels and datasets

#### `TableWidget` (Abstract)
- Base for table widgets
- Methods: `_fetch_data()`, `_process_table_data()`
- Returns columns and rows

### DataAggregator

**File**: `app/services/widgets/aggregators.py`

Centralizes all data fetching and enrichment logic:

```python
from app.services.widgets.aggregators import DataAggregator

aggregator = DataAggregator(session)

# Fetch detections for single line
df = await aggregator.fetch_detections(line_id=1, params=filter_params)

# Fetch detections for multiple lines
df = await aggregator.fetch_detections_multi_line([1, 2], params=filter_params)

# Enrich with metadata
df = aggregator.enrich_with_metadata(df)

# Resample time series
series = aggregator.resample_time_series(df, interval="hour")

# Aggregate by column
series = aggregator.aggregate_by_column(df, "area_name")

# Calculate total weight
total_weight = aggregator.calculate_total_weight(df)
```

**Features**:
- Single source for SQL query building
- Metadata enrichment (areas, products, lines)
- Time series resampling
- Column aggregation
- Weight calculations

### Specific Widget Types

#### KPIProductionWidget
- **Responsibility**: Total production count
- **Features**: Counts detections across lines
- **File**: `app/services/widgets/types/kpi_production.py`

#### KPIWeightWidget
- **Responsibility**: Total weight of production
- **Features**: Sums product weights
- **File**: `app/services/widgets/types/kpi_weight.py`

#### KPIOEEWidget
- **Responsibility**: OEE calculation
- **Status**: Placeholder (requires downtime integration)
- **File**: `app/services/widgets/types/kpi_oee.py`

#### KPIDowntimeWidget
- **Responsibility**: Downtime event count
- **Status**: Placeholder (requires downtime integration)
- **File**: `app/services/widgets/types/kpi_downtime.py`

#### LineChartWidget
- **Responsibility**: Time series visualization
- **Features**: Resamples data by interval
- **File**: `app/services/widgets/types/line_chart.py`

#### BarChartWidget
- **Responsibility**: Category distribution
- **Features**: Groups by area/product
- **File**: `app/services/widgets/types/bar_chart.py`

#### PieChartWidget
- **Responsibility**: Proportion visualization
- **Features**: Groups by product with colors
- **File**: `app/services/widgets/types/pie_chart.py`

#### ComparisonBarWidget
- **Responsibility**: Entrada vs Salida vs Descarte
- **Features**: Calculates difference
- **File**: `app/services/widgets/types/comparison_bar.py`

#### DowntimeTableWidget
- **Responsibility**: Downtime events table
- **Status**: Placeholder (requires downtime integration)
- **File**: `app/services/widgets/types/downtime_table.py`

### WidgetFactory

**File**: `app/services/widgets/factory.py`

Creates widget instances based on type:

```python
from app.services.widgets.factory import WidgetFactory
from app.services.widgets.base import WidgetConfig

config = WidgetConfig(
    widget_id=1,
    widget_name="Producción Total",
    widget_type="kpi_total_production"
)

widget_instance = WidgetFactory.create(config, session)
widget_data = await widget_instance.render(params)
```

**Features**:
- Type mapping (type string → class)
- Keyword detection from names (smart inference)
- Category detection (kpi, chart, table)
- Extensible via `register_widget_type()`

### WidgetRenderer (Updated)

**File**: `app/services/widgets/widget_renderer.py`

Now delegates to WidgetFactory:

```python
from app.services.widgets.widget_renderer import WidgetRenderer

renderer = WidgetRenderer(session)
widget_data = await renderer.render(widget_id=1, params=filter_params)
```

## Adding New Filter Types

To add a new filter type:

1. **Create filter class** in `app/services/filters/types/`:

```python
# app/services/filters/types/my_filter.py
from app.services.filters.base import InputFilter

class MyFilter(InputFilter):
    def validate_value(self, value):
        # Validation logic
        return True
    
    def get_default_value(self):
        return "default"
```

2. **Register in factory**:

```python
# In app/services/filters/factory.py
from app.services.filters.types.my_filter import MyFilter

FilterFactory.register_filter_type("my_filter", MyFilter)
```

3. **Add to types __init__.py**:

```python
# app/services/filters/types/__init__.py
from .my_filter import MyFilter

__all__ = ['MyFilter', ...]
```

## Adding New Widget Types

To add a new widget type:

1. **Create widget class** in `app/services/widgets/types/`:

```python
# app/services/widgets/types/my_widget.py
from app.services.widgets.base import ChartWidget
from app.services.widgets.aggregators import DataAggregator

class MyWidget(ChartWidget):
    async def _fetch_data(self, params):
        aggregator = DataAggregator(self.session)
        return await aggregator.fetch_detections_multi_line(
            aggregator.get_line_ids_from_params(params), 
            params
        )
    
    async def _process_chart_data(self, df, params):
        # Processing logic
        return {"labels": [], "datasets": []}
```

2. **Register in factory**:

```python
# In app/services/widgets/factory.py
from app.services.widgets.types.my_widget import MyWidget

WidgetFactory.register_widget_type(
    "my_widget", 
    MyWidget, 
    keywords=["custom", "special"]
)
```

3. **Add to types __init__.py**:

```python
# app/services/widgets/types/__init__.py
from .my_widget import MyWidget

__all__ = ['MyWidget', ...]
```

## Benefits

### Scalability
- **Easy to add new types**: Just create a class and register it
- **No modification of existing code**: Open/Closed Principle
- **Independent testing**: Each type can be tested in isolation
- **Parallel development**: Teams can work on different types simultaneously

### Maintainability
- **Single point of change**: Each class has one reason to change
- **Clear responsibilities**: Easy to understand what each class does
- **Reduced code duplication**: Shared logic in base classes and aggregators
- **Consistent patterns**: All types follow same structure

### Easy Parameter Access
- **Type-safe configs**: FilterConfig and WidgetConfig dataclasses
- **Validation built-in**: Each type validates its own parameters
- **Default values**: Centralized default value logic
- **Cascading support**: Parent-child dependencies handled cleanly

## Migration Notes

### Backward Compatibility
- Original `FilterResolver` interface preserved
- `WidgetRenderer` interface unchanged
- Returns same data structures
- No breaking changes to API endpoints

### Testing Strategy
1. Test each filter/widget type independently
2. Test factories with various configurations
3. Test aggregator methods with sample data
4. Integration tests with full rendering pipeline

## Example Usage

### Complete Filter Flow

```python
# 1. Get filter from cache
filter_data = metadata_cache.get_filter(1)

# 2. Resolve using FilterResolver
filter_dict = FilterResolver.resolve_filter(1, parent_values={"line_id": 1})

# Returns:
{
    "filter_id": 1,
    "filter_name": "Áreas",
    "param_name": "area_ids",
    "filter_type": "multiselect",
    "options": [
        {"value": 1, "label": "Área 1", "extra": {...}},
        {"value": 2, "label": "Área 2", "extra": {...}}
    ],
    "depends_on": "line_id",
    "required": False,
    "default_value": None,
    "ui_config": {...}
}
```

### Complete Widget Flow

```python
# 1. Get widget from cache
widget_data = metadata_cache.get_widget(1)

# 2. Create params from filters
params = FilterParams(
    line_ids=[1, 2],
    start_date=date(2024, 1, 1),
    end_date=date(2024, 1, 31),
    interval="day"
)

# 3. Render using WidgetRenderer
renderer = WidgetRenderer(session)
result = await renderer.render(widget_id=1, params=params)

# Returns:
{
    "widget_id": 1,
    "widget_name": "Producción Total",
    "widget_type": "kpi_total_production",
    "data": {
        "value": 15420,
        "unit": "unidades",
        "trend": None
    },
    "metadata": {
        "widget_category": "kpi",
        "line_ids": [1, 2]
    }
}
```

## Future Enhancements

1. **Async option loading**: For filters with expensive queries
2. **Option caching strategies**: TTL-based cache invalidation
3. **Filter presets**: Save/load filter combinations
4. **Widget templates**: Reusable widget configurations
5. **Dynamic aggregations**: User-defined aggregation functions
6. **Real-time updates**: WebSocket support for live data
7. **Export capabilities**: CSV/Excel export for widgets

## Conclusion

This architecture provides a solid foundation for scaling the dashboard system. Each component has a clear responsibility, shared logic is centralized, and adding new filter or widget types is straightforward and non-disruptive.
