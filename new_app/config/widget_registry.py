"""
Widget Registry Configuration.

Maps widget class names (stored in ``widget_catalog.widget_name``)
to their runtime metadata. This file is the ONLY place where you
register a new widget — the rest of the system discovers it
automatically via the Registry Pattern.

Keys:
  class_name → str  : must match widget_catalog.widget_name in DB.

Values: dict with:
  category     → str  : "kpi" | "chart" | "table" | "ranking"
  source_type  → str  : "internal" | "external"
  required_columns → list[str] : columns this widget needs from the
                                  master DataFrame (Data Scoping).
  api_source_id → str | None : key in external_apis.yml if source_type=="external".
  default_config → dict : any widget-specific defaults (Chart.js options, etc.)

To add a new widget:
  1. Create the widget class in new_app/services/widgets/types/
  2. Add an entry here.
  3. INSERT a row in widget_catalog with widget_name = class_name.
  Done. No other files to touch.
"""

WIDGET_REGISTRY: dict[str, dict] = {
    # ── KPIs ─────────────────────────────────────────────────
    "KpiTotalProduction": {
        "category": "kpi",
        "source_type": "internal",
        "required_columns": ["area_type"],
        "api_source_id": None,
        "default_config": {"unit": "unidades"},
    },
    "KpiTotalWeight": {
        "category": "kpi",
        "source_type": "internal",
        "required_columns": ["area_type", "product_weight"],
        "api_source_id": None,
        "default_config": {"unit": "kg"},
    },
    "KpiOee": {
        "category": "kpi",
        "source_type": "internal",
        "required_columns": ["area_type", "detected_at", "line_id"],
        "api_source_id": None,
        "default_config": {},
    },
    "KpiTotalDowntime": {
        "category": "kpi",
        "source_type": "internal",
        "required_columns": [],
        "api_source_id": None,
        "default_config": {},
    },
    "KpiAvailability": {
        "category": "kpi",
        "source_type": "internal",
        "required_columns": ["area_type", "detected_at", "line_id"],
        "api_source_id": None,
        "default_config": {},
    },
    "KpiPerformance": {
        "category": "kpi",
        "source_type": "internal",
        "required_columns": ["area_type", "detected_at", "line_id"],
        "api_source_id": None,
        "default_config": {},
    },
    "KpiQuality": {
        "category": "kpi",
        "source_type": "internal",
        "required_columns": ["area_type", "line_id"],
        "api_source_id": None,
        "default_config": {},
    },

    # ── Charts ───────────────────────────────────────────────
    "ProductionTimeChart": {
        "category": "chart",
        "source_type": "internal",
        "required_columns": ["detected_at", "area_type", "line_id", "product_name", "product_color"],
        "api_source_id": None,
        "default_config": {"curve_type": "smooth"},
    },
    "AreaDetectionChart": {
        "category": "chart",
        "source_type": "internal",
        "required_columns": ["area_name", "area_type"],
        "api_source_id": None,
        "default_config": {},
    },
    "ProductDistributionChart": {
        "category": "chart",
        "source_type": "internal",
        "required_columns": ["product_name", "product_color"],
        "api_source_id": None,
        "default_config": {},
    },
    "EntryOutputCompareChart": {
        "category": "chart",
        "source_type": "internal",
        "required_columns": ["detected_at", "area_type", "line_id"],
        "api_source_id": None,
        "default_config": {},
    },
    "ScatterChart": {
        "category": "chart",
        "source_type": "internal",
        "required_columns": [],
        "api_source_id": None,
        "default_config": {},
    },

    # ── Tables ───────────────────────────────────────────────
    "DowntimeTable": {
        "category": "table",
        "source_type": "internal",
        "required_columns": [],
        "api_source_id": None,
        "default_config": {},
    },

    # ── Ranking ──────────────────────────────────────────────
    "ProductRanking": {
        "category": "ranking",
        "source_type": "internal",
        "required_columns": ["product_name", "product_code", "product_color", "product_weight", "area_type"],
        "api_source_id": None,
        "default_config": {},
    },
    "LineStatusIndicator": {
        "category": "indicator",
        "source_type": "internal",
        "required_columns": ["line_id", "line_name"],
        "api_source_id": None,
        "default_config": {},
    },
    "MetricsSummary": {
        "category": "summary",
        "source_type": "internal",
        "required_columns": ["detected_at", "area_type", "line_id", "product_name", "product_weight"],
        "api_source_id": None,
        "default_config": {},
    },
    "EventFeed": {
        "category": "feed",
        "source_type": "internal",
        "required_columns": [],
        "api_source_id": None,
        "default_config": {"max_items": 50},
    },
}


# ── Frontend rendering configuration ────────────────────────────
#
# Maps each widget class to the Jinja partial and CSS Grid placement.
#
#   render     → selects the partial template.
#   chart_type → (charts only) tells ChartRenderer which builder to use.
#   chart_height → canvas height.
#   downtime_only → hide in multi-line mode.
#
# Grid layout uses auto-flow with a 3-column system.
# Each widget specifies:
#   col_span → how many columns to occupy (1-3, default: 1)
#   order    → display order; the grid auto-packs widgets left-to-right.
#
# Because there is NO explicit col/row, the grid fills naturally:
#   - If a widget is hidden, the next widget slides up — no gaps.
#   - "order" controls the visual sequence.
#   - "col_span: 3" = full-width row.
#
# To rearrange the dashboard, simply change order or col_span.
# No CSS or template changes needed.

WIDGET_RENDER_MAP: dict[str, dict] = {
    # ── 3 OEE sub-KPIs ───────────────────────────────────────
    "KpiAvailability":       {"render": "kpi",     "col_span": 1, "order": 1},
    "KpiPerformance":        {"render": "kpi",     "col_span": 1, "order": 2},
    "KpiQuality":            {"render": "kpi",     "col_span": 1, "order": 3},

    # ── Production Time Chart (full width) ───────────────────
    "ProductionTimeChart":   {"render": "chart", "chart_type": "line_chart",  "col_span": 4, "chart_height": "400px", "order": 4},

    # ── Pie Chart (2 cols) · OEE KPI (1 col) ────────────────
    "ProductDistributionChart": {"render": "chart", "chart_type": "pie_chart", "col_span": 2, "chart_height": "280px", "order": 5},
    "KpiOee":                {"render": "kpi_oee", "col_span": 1, "order": 0},

    # ── Production · Weight · Downtime KPIs ──────────────────
    "KpiTotalProduction":    {"render": "kpi",     "col_span": 1, "order": 7},
    "KpiTotalWeight":        {"render": "kpi",     "col_span": 1, "order": 8},
    "KpiTotalDowntime":      {"render": "kpi",     "col_span": 1, "order": 9, "downtime_only": True},

    # ── Area Detection · Product Ranking ─────────────────────
    "AreaDetectionChart":    {"render": "chart", "chart_type": "bar_chart",  "col_span": 1, "chart_height": "280px", "order": 11},
    "ProductRanking":        {"render": "table",   "col_span": 2, "order": 6},

    # ── Entry/Output Compare (full width) ────────────────────
    "EntryOutputCompareChart": {"render": "chart", "chart_type": "comparison_bar", "col_span": 4, "chart_height": "400px", "order": 12},

    # ── Scatter · Downtime Table ─────────────────────────────
    "ScatterChart":          {"render": "chart", "chart_type": "scatter_chart", "col_span": 1, "chart_height": "300px", "order": 13, "downtime_only": True},
    "DowntimeTable":         {"render": "table",   "col_span": 2, "order": 14   , "downtime_only": True},

    # ── Line Status · Metrics Summary ────────────────────────
    "LineStatusIndicator":   {"render": "indicator", "col_span": 1, "order": 10},
    "MetricsSummary":        {"render": "summary",   "col_span": 2, "order": 15},

    # ── Event Feed (full width) ──────────────────────────────
    "EventFeed":             {"render": "feed",      "col_span": 4, "order": 16},
}

# Number of columns in the dashboard grid.
GRID_COLUMNS = 4
