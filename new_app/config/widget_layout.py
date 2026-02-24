"""
Widget Layout Configuration — Camet Analytics Dashboard
========================================================

Define el posicionamiento visual de cada widget en el grid del dashboard.
Es la ÚNICA fuente de configuración de layout. No mezcla lógica de negocio.

Campos por widget:
  tab           → str   "produccion" | "oee"   pestaña donde aparece
  col_span      → int   1..4                   columnas que ocupa (grid de 4)
  row_span      → int   1..2                   (opcional) filas que ocupa
  order         → int                          orden de aparición en el grid
  downtime_only → bool  (opcional, default=False) ocultar en modo multi-línea

Grid columns: 4 (GRID_COLUMNS).

Para agregar un nuevo widget al layout, agregar una entrada aquí
con su widget_name (= nombre de clase) como clave.
"""

# Configuración global del layout
SHOW_OEE_TAB: bool = False

WIDGET_LAYOUT: dict[str, dict] = {

    # ── Tab: OEE ─────────────────────────────────────────────────────────
    "KpiOee":               {"tab": "oee",        "col_span": 1, "row_span": 1, "order": 0},
    "KpiAvailability":      {"tab": "oee",        "col_span": 1, "row_span": 1, "order": 1},
    "KpiPerformance":       {"tab": "oee",        "col_span": 1, "row_span": 1, "order": 2},
    "KpiQuality":           {"tab": "oee",        "col_span": 1, "row_span": 1, "order": 3},

    # ── Tab: Producción ───────────────────────────────────────────────────
    "ProductionTimeChart":      {"tab": "produccion", "col_span": 4, "row_span": 2, "order": 4},
    "ProductDistributionChart": {"tab": "produccion", "col_span": 2, "row_span": 2, "order": 5},
    "ProductRanking":           {"tab": "produccion", "col_span": 1, "row_span": 2, "order": 6},
    "KpiTotalProduction":       {"tab": "produccion", "col_span": 1, "row_span": 1, "order": 7},
    "KpiTotalWeight":           {"tab": "produccion", "col_span": 1, "row_span": 1, "order": 8},
    "KpiTotalDowntime":         {"tab": "produccion", "col_span": 1, "row_span": 1, "order": 9,  "downtime_only": True},
    "LineStatusIndicator":      {"tab": "produccion", "col_span": 1, "row_span": 1, "order": 10},
    "AreaDetectionChart":       {"tab": "produccion", "col_span": 2, "row_span": 2, "order": 11},
    "EntryOutputCompareChart":  {"tab": "produccion", "col_span": 4, "row_span": 2, "order": 12},
    "ScatterChart":             {"tab": "produccion", "col_span": 2, "row_span": 2, "order": 13, "downtime_only": True},
    "DowntimeTable":            {"tab": "produccion", "col_span": 2, "row_span": 2, "order": 14, "downtime_only": True},
    "MetricsSummary":           {"tab": "produccion", "col_span": 2, "row_span": 2, "order": 15},
    "EventFeed":                {"tab": "produccion", "col_span": 4, "row_span": 2, "order": 16},
}

# Number of grid columns (used in template)
GRID_COLUMNS: int = 4
