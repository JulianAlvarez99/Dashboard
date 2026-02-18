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
        "required_columns": ["detected_at", "line_id"],
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
        "required_columns": ["detected_at", "area_type", "line_id"],
        "api_source_id": None,
        "default_config": {"curve_type": "smooth"},
    },
    "AreaDetectionChart": {
        "category": "chart",
        "source_type": "internal",
        "required_columns": ["detected_at", "area_type"],
        "api_source_id": None,
        "default_config": {},
    },
    "ProductDistributionChart": {
        "category": "chart",
        "source_type": "internal",
        "required_columns": ["product_name"],
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
        "required_columns": ["product_name", "area_type"],
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
        "required_columns": ["detected_at", "area_type", "line_id"],
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
# Maps each widget class to the Jinja partial and grid size used by
# the dashboard template.  ``render`` selects the partial template,
# ``chart_type`` (if any) tells ChartRenderer which config builder
# to use, and ``size`` drives the CSS grid column span.

WIDGET_RENDER_MAP: dict[str, dict] = {
    # KPIs
    "KpiTotalProduction":    {"render": "kpi", "size": "small"},
    "KpiTotalWeight":        {"render": "kpi", "size": "small"},
    "KpiOee":                {"render": "kpi_oee", "size": "medium"},
    "KpiTotalDowntime":      {"render": "kpi", "size": "small", "downtime_only": True},
    "KpiAvailability":       {"render": "kpi", "size": "small"},
    "KpiPerformance":        {"render": "kpi", "size": "small"},
    "KpiQuality":            {"render": "kpi", "size": "small"},
    # Charts
    "ProductionTimeChart":   {"render": "chart", "chart_type": "line_chart",     "size": "large",  "chart_height": "300px"},
    "AreaDetectionChart":    {"render": "chart", "chart_type": "bar_chart",      "size": "medium", "chart_height": "250px"},
    "ProductDistributionChart": {"render": "chart", "chart_type": "pie_chart",   "size": "medium", "chart_height": "250px"},
    "EntryOutputCompareChart":  {"render": "chart", "chart_type": "comparison_bar", "size": "large",  "chart_height": "300px"},
    "ScatterChart":          {"render": "chart", "chart_type": "scatter_chart",  "size": "large",  "chart_height": "300px", "downtime_only": True},
    # Tables
    "DowntimeTable":         {"render": "table", "size": "large", "downtime_only": True},
    "ProductRanking":        {"render": "table", "size": "medium"},
    # Status / Summary / Feed
    "LineStatusIndicator":   {"render": "indicator", "size": "medium"},
    "MetricsSummary":        {"render": "summary", "size": "full"},
    "EventFeed":             {"render": "feed", "size": "medium"},
}

WIDGET_SIZE_CSS: dict[str, str] = {
    "small":  "col-span-1",
    "medium": "col-span-1 xl:col-span-1",
    "large":  "col-span-1 md:col-span-2",
    "full":   "col-span-full",
}
