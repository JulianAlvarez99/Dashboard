"""Widget Layout Configuration — Camet Analytics Dashboard
========================================================

Lightweight module providing:
  - GRID_COLUMNS: Number of grid columns for the dashboard layout
  - SHOW_OEE_TAB: Feature flag for OEE tab visibility

Layout attributes (tab, col_span, row_span, order, downtime_only) are now
defined directly in widget class attributes. See:
  @see new_app/services/widgets/base.py BaseWidget class attributes
  @see new_app/services/widgets/types/*.py for widget implementations
"""

from __future__ import annotations


def _get_show_oee_tab() -> bool:
    """Read SHOW_OEE_TAB from settings, defaulting to False."""
    try:
        from new_app.core.config import get_settings
        return get_settings().SHOW_OEE_TAB
    except Exception:
        return False


# ── Constants ────────────────────────────────────────────────────
GRID_COLUMNS: int = 4
SHOW_OEE_TAB: bool = _get_show_oee_tab()
