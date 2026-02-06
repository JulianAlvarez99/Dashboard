# Quick Start Guide - Refactored Architecture

This guide shows practical examples of how to use the refactored filter and widget systems.

## Table of Contents
1. [Working with Filters](#working-with-filters)
2. [Working with Widgets](#working-with-widgets)
3. [Common Patterns](#common-patterns)
4. [Debugging Tips](#debugging-tips)

---

## Working with Filters

### Example 1: Creating a Simple Dropdown Filter

```python
from app.services.filters.base import FilterConfig
from app.services.filters.factory import FilterFactory

# Define configuration
config = FilterConfig(
    filter_id=1,
    filter_name="Línea de Producción",
    param_name="line_id",
    filter_type="dropdown",
    options_source="production_line",
    required=True
)

# Create filter instance
filter_instance = FilterFactory.create(config)

# Get options
options = filter_instance.get_options()

# Validate a value
is_valid = filter_instance.validate_value(1)

# Get default value
default = filter_instance.get_default_value()
```

### Example 2: Cascading Filters (Areas dependent on Line)

```python
from app.services.filters.factory import FilterFactory
from app.services.filters.base import FilterConfig

# Line filter (parent)
line_config = FilterConfig(
    filter_id=1,
    filter_name="Línea",
    param_name="line_id",
    filter_type="dropdown",
    options_source="production_line"
)
line_filter = FilterFactory.create(line_config)
line_options = line_filter.get_options()

# Area filter (child - depends on line)
area_config = FilterConfig(
    filter_id=2,
    filter_name="Áreas",
    param_name="area_ids",
    filter_type="multiselect",
    options_source="area",
    depends_on="line_id"
)
area_filter = FilterFactory.create(area_config)

# Get options WITHOUT parent value (all areas)
all_areas = area_filter.get_options()

# Get options WITH parent value (filtered by line)
parent_values = {"line_id": 1}
filtered_areas = area_filter.get_options(parent_values)
```

### Example 3: Using FilterResolver (High-level API)

```python
from app.services.filters.filter_resolver import FilterResolver

# Resolve a single filter
filter_dict = FilterResolver.resolve_filter(
    filter_id=1,
    parent_values={"line_id": 1}
)

# Result:
# {
#     "filter_id": 1,
#     "filter_name": "Áreas",
#     "param_name": "area_ids",
#     "filter_type": "multiselect",
#     "options": [...],
#     "depends_on": "line_id",
#     "required": False,
#     ...
# }

# Resolve multiple filters
filters = FilterResolver.resolve_filters([1, 2, 3])

# Get options for HTMX cascade update
options = FilterResolver.get_filter_options(
    filter_id=2, 
    parent_values={"line_id": 1}
)
```

### Example 4: Date Range Filter

```python
from app.services.filters.base import FilterConfig
from app.services.filters.types.daterange import DateRangeFilter

config = FilterConfig(
    filter_id=10,
    filter_name="Rango de Fechas",
    param_name="date_range",
    filter_type="daterange",
    default_value={"days_back": 7}
)

date_filter = DateRangeFilter(config)

# Get default range (last 7 days)
default_range = date_filter.get_default_value()
# Returns: {"start_date": "2024-01-24", "end_date": "2024-01-31", ...}

# Validate a range
value = {
    "start_date": "2024-01-01",
    "end_date": "2024-01-31",
    "start_time": "00:00",
    "end_time": "23:59"
}
is_valid = date_filter.validate_value(value)

# Parse to datetime objects
datetime_range = date_filter.parse_to_datetime(value)
# Returns: {"start_datetime": datetime(...), "end_datetime": datetime(...)}
```

---

## Working with Widgets

### Example 1: Rendering a KPI Widget

```python
from app.services.widgets.widget_renderer import WidgetRenderer
from app.services.widgets.base import FilterParams
from datetime import date

# Create filter parameters
params = FilterParams(
    line_ids=[1, 2],
    start_date=date(2024, 1, 1),
    end_date=date(2024, 1, 31)
)

# Render widget
renderer = WidgetRenderer(session)
widget_data = await renderer.render(widget_id=1, params=params)

# Result:
# {
#     "widget_id": 1,
#     "widget_name": "Producción Total",
#     "widget_type": "kpi_total_production",
#     "data": {
#         "value": 15420,
#         "unit": "unidades",
#         "trend": None
#     },
#     "metadata": {...}
# }
```

### Example 2: Direct Widget Creation with WidgetFactory

```python
from app.services.widgets.factory import WidgetFactory
from app.services.widgets.base import WidgetConfig, FilterParams

# Create widget configuration
config = WidgetConfig(
    widget_id=5,
    widget_name="Gráfico de Línea",
    widget_type="line_chart",
    size="large",
    ui_config={"color": "#3b82f6"}
)

# Create widget instance
widget = WidgetFactory.create(config, session)

# Render with parameters
params = FilterParams(
    line_id=1,
    start_date=date(2024, 1, 1),
    end_date=date(2024, 1, 31),
    interval="day"
)

result = await widget.render(params)
```

### Example 3: Using DataAggregator Directly

```python
from app.services.widgets.aggregators import DataAggregator
from app.services.widgets.base import FilterParams

aggregator = DataAggregator(session)

# Fetch raw detections
params = FilterParams(
    line_id=1,
    start_date=date(2024, 1, 1),
    end_date=date(2024, 1, 31)
)

df = await aggregator.fetch_detections(line_id=1, params=params)

# Enrich with metadata
df = aggregator.enrich_with_metadata(df)

# Now df has columns: area_name, product_name, product_weight, etc.

# Aggregate by area
area_counts = aggregator.aggregate_by_column(df, "area_name")

# Calculate total weight
total_weight = aggregator.calculate_total_weight(df)

# Resample time series
hourly_series = aggregator.resample_time_series(df, interval="hour")
```

### Example 4: Creating a Custom Widget

```python
from app.services.widgets.base import ChartWidget, FilterParams, WidgetData
from app.services.widgets.aggregators import DataAggregator
import pandas as pd

class CustomProductionTrendWidget(ChartWidget):
    """Custom widget showing production trend with forecast"""
    
    async def _fetch_data(self, params: FilterParams) -> pd.DataFrame:
        aggregator = DataAggregator(self.session)
        line_ids = aggregator.get_line_ids_from_params(params)
        
        df = await aggregator.fetch_detections_multi_line(line_ids, params)
        
        if not df.empty:
            df = aggregator.enrich_with_metadata(df)
        
        return df
    
    async def _process_chart_data(
        self, 
        df: pd.DataFrame, 
        params: FilterParams
    ) -> dict:
        aggregator = DataAggregator(self.session)
        
        # Resample to daily data
        daily_series = aggregator.resample_time_series(df, "day")
        
        # Calculate moving average (simple forecast)
        import numpy as np
        ma_values = np.convolve(
            daily_series.values, 
            np.ones(3)/3, 
            mode='valid'
        )
        
        return {
            "labels": [str(d) for d in daily_series.index],
            "datasets": [
                {
                    "label": "Producción Real",
                    "data": daily_series.values.tolist(),
                    "borderColor": "#3b82f6"
                },
                {
                    "label": "Tendencia (MA3)",
                    "data": [None, None] + ma_values.tolist(),
                    "borderColor": "#f59e0b",
                    "borderDash": [5, 5]
                }
            ]
        }

# Register the custom widget
from app.services.widgets.factory import WidgetFactory

WidgetFactory.register_widget_type(
    "custom_production_trend",
    CustomProductionTrendWidget,
    keywords=["tendencia", "trend", "forecast"]
)
```

---

## Common Patterns

### Pattern 1: Full Dashboard Rendering Pipeline

```python
async def render_dashboard(user, filter_values):
    """Complete pipeline: filters → params → widgets"""
    
    # Step 1: Get layout configuration
    layout = metadata_cache.get_layout(user.layout_id)
    
    # Step 2: Resolve filters with user values
    filter_ids = layout["filter_ids"]
    filters = FilterResolver.resolve_filters(filter_ids)
    
    # Step 3: Parse filter values into FilterParams
    params = FilterParams.from_dict(filter_values)
    
    # Step 4: Render all widgets
    renderer = WidgetRenderer(session)
    widgets_data = []
    
    for widget_id in layout["widget_ids"]:
        widget_data = await renderer.render(widget_id, params)
        if widget_data:
            widgets_data.append(widget_data.to_dict())
    
    return {
        "filters": filters,
        "widgets": widgets_data,
        "layout": layout
    }
```

### Pattern 2: Filter Cascade Handler (HTMX Endpoint)

```python
from fastapi import APIRouter, Query

router = APIRouter()

@router.get("/api/filters/{filter_id}/options")
async def get_filter_options(
    filter_id: int,
    line_id: int = Query(None),
    area_ids: list[int] = Query(None)
):
    """Get filter options based on parent values"""
    
    parent_values = {}
    if line_id:
        parent_values["line_id"] = line_id
    if area_ids:
        parent_values["area_ids"] = area_ids
    
    options = FilterResolver.get_filter_options(
        filter_id=filter_id,
        parent_values=parent_values
    )
    
    return {"options": options}
```

### Pattern 3: Widget Refresh with New Filters

```python
from fastapi import APIRouter, Body

router = APIRouter()

@router.post("/api/widgets/{widget_id}/refresh")
async def refresh_widget(
    widget_id: int,
    filter_values: dict = Body(...)
):
    """Refresh a single widget with new filter values"""
    
    # Parse filter values
    params = FilterParams.from_dict(filter_values)
    
    # Render widget
    renderer = WidgetRenderer(session)
    widget_data = await renderer.render(widget_id, params)
    
    if not widget_data:
        return {"error": "Widget not found"}
    
    return widget_data.to_dict()
```

### Pattern 4: Batch Widget Rendering

```python
async def render_widgets_batch(widget_ids: list[int], params: FilterParams):
    """Render multiple widgets in parallel"""
    
    import asyncio
    
    renderer = WidgetRenderer(session)
    
    # Create tasks for parallel execution
    tasks = [
        renderer.render(widget_id, params)
        for widget_id in widget_ids
    ]
    
    # Execute in parallel
    results = await asyncio.gather(*tasks)
    
    # Filter out None results
    return [r.to_dict() for r in results if r is not None]
```

---

## Debugging Tips

### Tip 1: Checking Filter Configuration

```python
from app.services.filters.filter_resolver import FilterResolver
import json

# Get full filter configuration
filter_dict = FilterResolver.resolve_filter(filter_id=1)

# Pretty print for debugging
print(json.dumps(filter_dict, indent=2, default=str))
```

### Tip 2: Inspecting Widget Data Flow

```python
from app.services.widgets.widget_renderer import WidgetRenderer
from app.services.widgets.aggregators import DataAggregator

# Step-by-step debugging
renderer = WidgetRenderer(session)

# 1. Check widget config
widget_data = metadata_cache.get_widget(widget_id)
print(f"Widget metadata: {widget_data}")

# 2. Check params
print(f"Filter params: {params.to_dict()}")

# 3. Check raw data
aggregator = DataAggregator(session)
df = await aggregator.fetch_detections(line_id=1, params=params)
print(f"Rows fetched: {len(df)}")
print(f"Columns: {df.columns.tolist()}")

# 4. Check enriched data
df = aggregator.enrich_with_metadata(df)
print(f"Enriched columns: {df.columns.tolist()}")
print(f"Sample:\n{df.head()}")
```

### Tip 3: Testing Individual Filter Types

```python
from app.services.filters.factory import FilterFactory

# Get supported types
supported = FilterFactory.get_supported_types()
print(f"Supported filter types: {supported}")

# Test each type
for filter_type in ["dropdown", "multiselect", "daterange"]:
    config = FilterConfig(
        filter_id=999,
        filter_name="Test",
        param_name="test",
        filter_type=filter_type,
        options_source="production_line"
    )
    
    filter_instance = FilterFactory.create(config)
    print(f"{filter_type}: {type(filter_instance).__name__}")
```

### Tip 4: Measuring Widget Performance

```python
import time

async def measure_widget_performance(widget_id, params):
    """Measure rendering time for optimization"""
    
    renderer = WidgetRenderer(session)
    
    start = time.time()
    result = await renderer.render(widget_id, params)
    end = time.time()
    
    elapsed = (end - start) * 1000  # Convert to ms
    
    print(f"Widget {widget_id} rendered in {elapsed:.2f}ms")
    
    if result:
        data_size = len(str(result.data))
        print(f"Data size: {data_size} bytes")
    
    return result
```

### Tip 5: Validating Filter Values

```python
def validate_dashboard_filters(filter_ids, user_values):
    """Validate all filter values before rendering"""
    
    errors = []
    
    for filter_id in filter_ids:
        filter_dict = FilterResolver.resolve_filter(filter_id)
        if not filter_dict:
            errors.append(f"Filter {filter_id} not found")
            continue
        
        param_name = filter_dict["param_name"]
        value = user_values.get(param_name)
        
        # Create filter instance for validation
        config = FilterConfig(**{
            k: v for k, v in filter_dict.items()
            if k in FilterConfig.__annotations__
        })
        
        filter_instance = FilterFactory.create(config)
        
        if not filter_instance.validate_value(value):
            errors.append(
                f"Invalid value for {param_name}: {value}"
            )
    
    return errors
```

---

## Advanced Usage

### Creating a Filter Preset System

```python
class FilterPresetManager:
    """Save and load filter combinations"""
    
    @staticmethod
    async def save_preset(user_id: int, name: str, filter_values: dict):
        """Save a filter preset"""
        preset = {
            "user_id": user_id,
            "name": name,
            "filter_values": filter_values,
            "created_at": datetime.now()
        }
        # Save to database
        await db.execute(
            "INSERT INTO filter_presets VALUES (...)",
            preset
        )
    
    @staticmethod
    async def load_preset(preset_id: int) -> dict:
        """Load a filter preset"""
        result = await db.execute(
            "SELECT filter_values FROM filter_presets WHERE id = :id",
            {"id": preset_id}
        )
        return result["filter_values"]
    
    @staticmethod
    async def apply_preset(preset_id: int):
        """Load and validate a preset"""
        filter_values = await FilterPresetManager.load_preset(preset_id)
        
        # Validate all values are still valid
        errors = validate_dashboard_filters(
            filter_ids=[...],
            user_values=filter_values
        )
        
        if errors:
            raise ValueError(f"Preset validation failed: {errors}")
        
        return FilterParams.from_dict(filter_values)
```

---

## Summary

This refactored architecture provides:

✅ **Clear separation of concerns** - Each filter/widget type handles its own logic  
✅ **Easy extensibility** - Add new types without modifying existing code  
✅ **Reusable components** - DataAggregator eliminates duplication  
✅ **Type safety** - Dataclasses provide structure and validation  
✅ **Testability** - Each component can be tested independently  
✅ **Performance** - Caching and efficient data pipelines  

Use the patterns above as templates for your specific dashboard requirements!
