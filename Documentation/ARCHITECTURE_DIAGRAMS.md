# Architecture Diagrams

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         DASHBOARD SYSTEM                         │
│                                                                  │
│  ┌──────────────────────┐         ┌──────────────────────┐      │
│  │   FILTER SYSTEM      │         │   WIDGET SYSTEM      │      │
│  │                      │         │                      │      │
│  │  • FilterResolver    │────────▶│  • WidgetRenderer    │      │
│  │  • FilterFactory     │  Params │  • WidgetFactory     │      │
│  │  • Filter Types      │         │  • Widget Types      │      │
│  │  • Base Classes      │         │  • DataAggregator    │      │
│  └──────────────────────┘         └──────────────────────┘      │
│           │                                    │                 │
│           │                                    │                 │
│           ▼                                    ▼                 │
│  ┌──────────────────────────────────────────────────────┐       │
│  │              METADATA CACHE                          │       │
│  │  • Production Lines  • Products  • Filters           │       │
│  │  • Areas             • Shifts    • Widgets           │       │
│  └──────────────────────────────────────────────────────┘       │
│                              │                                   │
│                              ▼                                   │
│                    ┌──────────────────┐                         │
│                    │  DATABASE        │                         │
│                    │  • Global DB     │                         │
│                    │  • Tenant DBs    │                         │
│                    └──────────────────┘                         │
└─────────────────────────────────────────────────────────────────┘
```

## Filter System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      FILTER RESOLVER                             │
│                  (Entry Point / Facade)                          │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
         ┌─────────────────────┐
         │  FILTER FACTORY     │
         │                     │
         │  create(config)     │────┐
         └─────────────────────┘    │
                                    │
                                    ▼
    ┌──────────────────────────────────────────────────────────┐
    │                    BASE CLASSES                           │
    ├──────────────────────────────────────────────────────────┤
    │                                                           │
    │  ┌─────────────────┐  ┌──────────────┐  ┌────────────┐  │
    │  │  BaseFilter     │  │ OptionsFilter│  │InputFilter │  │
    │  │  (Abstract)     │  │ (Abstract)   │  │(Abstract)  │  │
    │  └────────┬────────┘  └──────┬───────┘  └─────┬──────┘  │
    │           │                   │                │          │
    └───────────┼───────────────────┼────────────────┼──────────┘
                │                   │                │
                ▼                   ▼                ▼
    ┌───────────────────────────────────────────────────────────┐
    │                    CONCRETE TYPES                          │
    ├───────────────────────────────────────────────────────────┤
    │                                                            │
    │  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐      │
    │  │ DropdownF.  │  │ MultiselectF.│  │DateRangeF.  │      │
    │  └─────────────┘  └──────────────┘  └─────────────┘      │
    │                                                            │
    │  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐      │
    │  │  TextF.     │  │  NumberF.    │  │  ToggleF.   │      │
    │  └─────────────┘  └──────────────┘  └─────────────┘      │
    │                                                            │
    └────────────────────────────────────────────────────────────┘

RESPONSIBILITIES:
━━━━━━━━━━━━━━━━━
• BaseFilter:      Interface + common methods
• OptionsFilter:   Option loading + caching
• InputFilter:     Input validation only
• Dropdown:        Single selection from cache
• Multiselect:     Multiple selection from cache
• DateRange:       Date/time range handling
• Text:            Free text validation
• Number:          Numeric validation
• Toggle:          Boolean handling
```

## Widget System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     WIDGET RENDERER                              │
│                  (Entry Point / Facade)                          │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
         ┌─────────────────────┐
         │  WIDGET FACTORY     │
         │                     │
         │  create(config,     │────┐
         │         session)    │    │
         └─────────────────────┘    │
                                    │
                                    ▼
    ┌──────────────────────────────────────────────────────────┐
    │                    BASE CLASSES                           │
    ├──────────────────────────────────────────────────────────┤
    │                                                           │
    │  ┌───────────┐  ┌───────────┐  ┌──────────┐  ┌────────┐ │
    │  │BaseWidget │  │KPIWidget  │  │ChartWidget│ │TableW. │ │
    │  │(Abstract) │  │(Abstract) │  │(Abstract) │ │(Abs.)  │ │
    │  └─────┬─────┘  └─────┬─────┘  └─────┬────┘ └───┬────┘ │
    │        │              │              │            │       │
    └────────┼──────────────┼──────────────┼────────────┼───────┘
             │              │              │            │
             ▼              ▼              ▼            ▼
    ┌────────────────────────────────────────────────────────────┐
    │                  CONCRETE WIDGET TYPES                      │
    ├────────────────────────────────────────────────────────────┤
    │                                                             │
    │  KPI Widgets:                                               │
    │  ┌───────────────┐  ┌──────────────┐  ┌───────────────┐   │
    │  │ Production    │  │ Weight       │  │ OEE           │   │
    │  └───────────────┘  └──────────────┘  └───────────────┘   │
    │  ┌───────────────┐                                         │
    │  │ Downtime      │                                         │
    │  └───────────────┘                                         │
    │                                                             │
    │  Chart Widgets:                                             │
    │  ┌───────────────┐  ┌──────────────┐  ┌───────────────┐   │
    │  │ Line Chart    │  │ Bar Chart    │  │ Pie Chart     │   │
    │  └───────────────┘  └──────────────┘  └───────────────┘   │
    │  ┌───────────────┐                                         │
    │  │ Comparison Bar│                                         │
    │  └───────────────┘                                         │
    │                                                             │
    │  Table Widgets:                                             │
    │  ┌───────────────┐                                         │
    │  │Downtime Table │                                         │
    │  └───────────────┘                                         │
    │                                                             │
    └─────────────────────────────────────────────────────────────┘

              ┌──────────────────────────────────┐
              │      DATA AGGREGATOR             │
              │  (Shared Data Fetching Logic)    │
              ├──────────────────────────────────┤
              │ • fetch_detections()             │
              │ • fetch_detections_multi_line()  │
              │ • enrich_with_metadata()         │
              │ • enrich_with_line_metadata()    │
              │ • resample_time_series()         │
              │ • aggregate_by_column()          │
              │ • calculate_total_weight()       │
              └──────────────────────────────────┘

RESPONSIBILITIES:
━━━━━━━━━━━━━━━━━
• BaseWidget:        Interface + common methods
• KPIWidget:         Single value + trend calculation
• ChartWidget:       Labels + datasets structure
• TableWidget:       Columns + rows structure
• Specific Types:    Concrete implementations
• DataAggregator:    Centralized data fetching/processing
```

## Data Flow Diagram

```
┌──────────┐
│  USER    │
│ SELECTS  │
│ FILTERS  │
└────┬─────┘
     │
     ▼
┌─────────────────────────────────────────────┐
│  1. FILTER RESOLUTION                       │
│                                             │
│  FilterResolver.resolve_filters()           │
│         │                                   │
│         ▼                                   │
│  FilterFactory.create()                     │
│         │                                   │
│         ▼                                   │
│  filter.get_options()                       │
│                                             │
└────┬────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────┐
│  2. PARAMETER CONSTRUCTION                  │
│                                             │
│  FilterParams.from_dict(filter_values)      │
│     {                                       │
│       line_ids: [1, 2],                     │
│       start_date: "2024-01-01",             │
│       end_date: "2024-01-31",               │
│       interval: "day"                       │
│     }                                       │
│                                             │
└────┬────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────┐
│  3. WIDGET RENDERING                        │
│                                             │
│  WidgetRenderer.render(widget_id, params)   │
│         │                                   │
│         ▼                                   │
│  WidgetFactory.create(config, session)      │
│         │                                   │
│         ▼                                   │
│  widget.render(params)                      │
│         │                                   │
│         ▼                                   │
│  DataAggregator.fetch_detections()          │
│         │                                   │
│         ▼                                   │
│  DataAggregator.enrich_with_metadata()      │
│         │                                   │
│         ▼                                   │
│  widget._process_chart_data()               │
│                                             │
└────┬────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────┐
│  4. RESPONSE                                │
│                                             │
│  WidgetData {                               │
│    widget_id: 1,                            │
│    widget_name: "Producción Total",         │
│    widget_type: "kpi_total_production",     │
│    data: {                                  │
│      value: 15420,                          │
│      unit: "unidades"                       │
│    },                                       │
│    metadata: {...}                          │
│  }                                          │
│                                             │
└────┬────────────────────────────────────────┘
     │
     ▼
┌──────────┐
│ DISPLAY  │
│    TO    │
│   USER   │
└──────────┘
```

## Class Hierarchy - Filters

```
BaseFilter (Abstract)
│
├── OptionsFilter (Abstract)
│   │
│   ├── DropdownFilter
│   │   └── Methods:
│   │       • _load_options()
│   │       • _load_production_lines()
│   │       • _load_areas()
│   │       • _load_products()
│   │       • _load_shifts()
│   │
│   └── MultiselectFilter
│       └── Inherits: DropdownFilter
│           Overrides:
│           • validate_value() - validates list
│           • get_default_value() - returns list
│
└── InputFilter (Abstract)
    │
    ├── DateRangeFilter
    │   └── Methods:
    │       • validate_value() - checks date range
    │       • get_default_value() - last N days
    │       • parse_to_datetime() - converts to datetime
    │
    ├── TextFilter
    │   └── Methods:
    │       • validate_value() - min/max length
    │       • get_default_value() - empty string
    │
    ├── NumberFilter
    │   └── Methods:
    │       • validate_value() - min/max value
    │       • get_default_value() - zero
    │
    └── ToggleFilter
        └── Methods:
            • validate_value() - boolean check
            • get_default_value() - false
```

## Class Hierarchy - Widgets

```
BaseWidget (Abstract)
│
├── KPIWidget (Abstract)
│   │   Methods:
│   │   • render() - calculates KPI + trend
│   │   • _calculate_value() (abstract)
│   │   • _calculate_trend()
│   │   • _get_unit() (abstract)
│   │
│   ├── KPIProductionWidget
│   │   • _calculate_value() - count detections
│   │   • _get_unit() - "unidades"
│   │
│   ├── KPIWeightWidget
│   │   • _calculate_value() - sum weights
│   │   • _get_unit() - "kg"
│   │
│   ├── KPIOEEWidget
│   │   • _calculate_value() - OEE formula
│   │   • _get_unit() - "%"
│   │
│   └── KPIDowntimeWidget
│       • _calculate_value() - count downtime
│       • _get_unit() - "paradas"
│
├── ChartWidget (Abstract)
│   │   Methods:
│   │   • render() - fetch + process data
│   │   • _fetch_data() (abstract)
│   │   • _process_chart_data() (abstract)
│   │
│   ├── LineChartWidget
│   │   • _fetch_data() - detections
│   │   • _process_chart_data() - resample time series
│   │
│   ├── BarChartWidget
│   │   • _fetch_data() - detections + enrich
│   │   • _process_chart_data() - group by area
│   │
│   ├── PieChartWidget
│   │   • _fetch_data() - detections + enrich
│   │   • _process_chart_data() - group by product
│   │
│   └── ComparisonBarWidget
│       • _fetch_data() - detections + enrich
│       • _process_chart_data() - group by area_type
│
└── TableWidget (Abstract)
    │   Methods:
    │   • render() - fetch + process table
    │   • _fetch_data() (abstract)
    │   • _process_table_data() (abstract)
    │
    └── DowntimeTableWidget
        • _fetch_data() - downtime events
        • _process_table_data() - format rows
```

## SRP & DRY Implementation

```
┌────────────────────────────────────────────────────────────────┐
│                  SINGLE RESPONSIBILITY PRINCIPLE               │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Each class has ONE reason to change:                          │
│                                                                │
│  ┌──────────────────┐    ┌──────────────────┐                 │
│  │ DropdownFilter   │    │ DateRangeFilter  │                 │
│  │                  │    │                  │                 │
│  │ Responsibility:  │    │ Responsibility:  │                 │
│  │ Load options     │    │ Handle date      │                 │
│  │ from cache       │    │ range validation │                 │
│  └──────────────────┘    └──────────────────┘                 │
│                                                                │
│  ┌──────────────────┐    ┌──────────────────┐                 │
│  │KPIProductionW.   │    │ LineChartWidget  │                 │
│  │                  │    │                  │                 │
│  │ Responsibility:  │    │ Responsibility:  │                 │
│  │ Calculate total  │    │ Time series      │                 │
│  │ production count │    │ visualization    │                 │
│  └──────────────────┘    └──────────────────┘                 │
│                                                                │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│                   DON'T REPEAT YOURSELF                        │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Shared logic extracted to common components:                  │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │              BASE CLASSES                                 │ │
│  │  • Common validation logic                                │ │
│  │  • Common serialization (to_dict)                         │ │
│  │  • Common error handling                                  │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │              DATA AGGREGATOR                              │ │
│  │  • SQL query building                                     │ │
│  │  • Metadata enrichment                                    │ │
│  │  • Time series resampling                                 │ │
│  │  • Column aggregation                                     │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │              FACTORIES                                    │ │
│  │  • Centralized object creation                            │ │
│  │  • Type mapping logic                                     │ │
│  │  • Registration mechanism                                 │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │              OPTIONS FILTER BASE                          │ │
│  │  • Option loading pattern                                 │ │
│  │  • Option caching                                         │ │
│  │  • Shared validation                                      │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

## Extension Points

```
┌────────────────────────────────────────────────────────────────┐
│                    ADDING NEW FILTER TYPE                      │
└────────────────────────────────────────────────────────────────┘

    1. Create Class                 2. Register
    ───────────────────            ───────────────────
    
    class MyFilter:                FilterFactory.register(
        def get_options():             "my_filter",
            ...                        MyFilter
        def validate():            )
            ...
    
    
    ✅ No changes to existing code
    ✅ Follows Open/Closed Principle


┌────────────────────────────────────────────────────────────────┐
│                    ADDING NEW WIDGET TYPE                      │
└────────────────────────────────────────────────────────────────┘

    1. Create Class                 2. Register
    ───────────────────            ───────────────────
    
    class MyWidget:                WidgetFactory.register(
        async def render():            "my_widget",
            aggregator = ...           MyWidget,
            df = await fetch()         keywords=["custom"]
            return process(df)     )
    
    
    ✅ Uses DataAggregator (DRY)
    ✅ Follows same patterns


┌────────────────────────────────────────────────────────────────┐
│                  CUSTOMIZING DATA AGGREGATION                  │
└────────────────────────────────────────────────────────────────┘

    Add methods to DataAggregator:
    
    class DataAggregator:
        
        async def fetch_custom_data(self, ...):
            # Custom SQL query
            ...
        
        def apply_custom_transform(self, df):
            # Custom pandas operation
            ...
    
    
    ✅ Available to all widgets
    ✅ Reusable across types
```
