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

from __future__ import annotations

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

# ── Feature flags ────────────────────────────────────────────────
# Reads from settings so it can be toggled via environment variable.
# Falls back to False if settings are unavailable at import time.

def _get_show_oee_tab() -> bool:
    try:
        from new_app.core.config import get_settings  # lazy import
        return get_settings().SHOW_OEE_TAB
    except Exception:
        return False


SHOW_OEE_TAB: bool = _get_show_oee_tab()

WIDGET_LAYOUT: dict[str, dict] = {

    # ── Tab: OEE ─────────────────────────────────────────────────────────
    "KpiOee":               {"tab": "oee",        "col_span": 1, "row_span": 1, "order": 0},
    "KpiAvailability":      {"tab": "oee",        "col_span": 1, "row_span": 1, "order": 1},
    "KpiPerformance":       {"tab": "oee",        "col_span": 1, "row_span": 1, "order": 2},
    "KpiQuality":           {"tab": "oee",        "col_span": 1, "row_span": 1, "order": 3},

    # ── Tab: Producción ───────────────────────────────────────────────────
    "ProductionTimeChart":      {"tab": "produccion", "col_span": 4, "row_span": 2, "order": 4},
    "ProductDistributionChart": {"tab": "produccion", "col_span": 3, "row_span": 2, "order": 5},
    "ProductRanking":           {"tab": "produccion", "col_span": 1, "row_span": 2, "order": 6},
    "KpiTotalProduction":       {"tab": "produccion", "col_span": 1, "row_span": 1, "order": 7},
    "KpiTotalWeight":           {"tab": "produccion", "col_span": 1, "row_span": 1, "order": 8},
    "KpiTotalDowntime":         {"tab": "produccion", "col_span": 1, "row_span": 1, "order": 9,  "downtime_only": True},
    "LineStatusIndicator":      {"tab": "produccion", "col_span": 1, "row_span": 1, "order": 10},
    "KpiRejectedRate":          {"tab": "produccion", "col_span": 1, "row_span": 1, "order": 17},
    "AreaDetectionChart":       {"tab": "produccion", "col_span": 2, "row_span": 2, "order": 11},
    "EntryOutputCompareChart":  {"tab": "produccion", "col_span": 4, "row_span": 2, "order": 12},
    "ScatterChart":             {"tab": "produccion", "col_span": 2, "row_span": 2, "order": 13, "downtime_only": True},
    "DowntimeTable":            {"tab": "produccion", "col_span": 3, "row_span": 2, "order": 14, "downtime_only": True},
    "MetricsSummary":           {"tab": "produccion", "col_span": 2, "row_span": 2, "order": 15},
    "EventFeed":                {"tab": "produccion", "col_span": 4, "row_span": 2, "order": 16},
}

# Number of grid columns (used in template)
GRID_COLUMNS: int = 4

# Valid tab identifiers
_VALID_TABS: frozenset[str] = frozenset({"produccion", "oee"})
_REQUIRED_KEYS: frozenset[str] = frozenset({"tab", "col_span", "order"})


# ── Startup validation ───────────────────────────────────────────

def validate_layout_consistency() -> List[str]:
    """
    Validate ``WIDGET_LAYOUT`` at startup and return a list of warning messages.

    Checks:
    - All required keys (tab, col_span, order) are present.
    - ``tab`` is a known value ("produccion" | "oee").
    - ``col_span`` is in [1, GRID_COLUMNS].
    - ``order`` values are unique (duplicate order causes non-deterministic rendering).
    - OEE widgets are defined but ``SHOW_OEE_TAB=False`` (surfaced as info, not error).

    Raises ``ValueError`` if any hard constraint is violated so the FastAPI
    lifespan hook can prevent the app from starting with a broken layout.
    """
    errors: List[str] = []
    warnings: List[str] = []
    seen_orders: Dict[int, str] = {}

    for widget_name, cfg in WIDGET_LAYOUT.items():
        # ── Required keys ───────────────────────────────────────
        missing = _REQUIRED_KEYS - cfg.keys()
        if missing:
            errors.append(f"[{widget_name}] Missing required keys: {missing}")
            continue

        # ── Tab validation ──────────────────────────────────────
        tab = cfg["tab"]
        if tab not in _VALID_TABS:
            errors.append(
                f"[{widget_name}] Unknown tab '{tab}'. Valid tabs: {sorted(_VALID_TABS)}"
            )

        # ── col_span validation ─────────────────────────────────
        col_span = cfg["col_span"]
        if not (1 <= col_span <= GRID_COLUMNS):
            errors.append(
                f"[{widget_name}] col_span={col_span} out of range [1, {GRID_COLUMNS}]"
            )

        # ── Duplicate order detection ───────────────────────────
        order = cfg["order"]
        if order in seen_orders:
            warnings.append(
                f"[{widget_name}] Duplicate order={order} also used by "
                f"'{seen_orders[order]}' — rendering order will be non-deterministic"
            )
        else:
            seen_orders[order] = widget_name

    # ── OEE tab hidden but widgets defined ──────────────────────
    oee_widgets = [n for n, c in WIDGET_LAYOUT.items() if c.get("tab") == "oee"]
    if oee_widgets and not SHOW_OEE_TAB:
        warnings.append(
            f"SHOW_OEE_TAB=False but {len(oee_widgets)} OEE widgets are defined "
            f"({', '.join(oee_widgets)}). They will be hidden in the UI."
        )

    # ── Emit warnings to log ─────────────────────────────────────
    for w in warnings:
        logger.warning("[LayoutValidation] %s", w)

    if errors:
        raise ValueError(
            "WIDGET_LAYOUT has configuration errors:\n"
            + "\n".join(f"  • {e}" for e in errors)
        )

    logger.info(
        "[LayoutValidation] OK — %d widgets validated (%d warnings).",
        len(WIDGET_LAYOUT),
        len(warnings),
    )
    return warnings
