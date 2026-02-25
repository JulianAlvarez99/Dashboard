"""
Dashboard routes — Renders the filter panel and widget grid.

After login the user lands here. The route:
1. Loads ``layout_config`` from ``dashboard_template`` for the user's
   tenant + role to determine which widgets and filters are enabled.
2. Enriches each widget with frontend rendering metadata:
   - Render behavior (render_type, chart_type) from widget class attributes.
   - Layout positioning (tab, col_span, order) from ``WIDGET_LAYOUT``.
3. Passes only the enabled filters and enriched widgets to the template.
4. The frontend JS sends filter submissions to ``POST /api/v1/dashboard/data``.
"""

import logging

import httpx

from flask import Blueprint, render_template, session

from new_app.routes.auth import login_required, get_current_user
from new_app.core.config import get_settings
from new_app.config.widget_layout    import WIDGET_LAYOUT, GRID_COLUMNS, SHOW_OEE_TAB
from new_app.services.widgets.engine import widget_engine

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


@dashboard_bp.route("/")
@login_required
def index():
    """
    Render the dashboard shell.

    This route only provides the **initial page structure**:
      - Filter panel (rendered via Jinja2 from layout config)
      - Empty widget grid (populated by JS calling the orchestrator API)

    The actual widget data is fetched client-side via:
      ``POST /api/v1/dashboard/data`` → DashboardOrchestrator
    """
    user = get_current_user()
    settings = get_settings()
    api_base = settings.API_BASE_URL

    tenant_id = user.get("tenant_id")
    role = user.get("role", "ADMIN")

    # ── 1. Load layout config (widget + filter IDs) ──────────
    layout_data = _fetch_layout(api_base, tenant_id, role)

    # ── 2. Fetch only the enabled filters ────────────────────
    enabled_filter_ids = (
        layout_data.get("enabled_filter_ids", [])
        if layout_data
        else []
    )
    filters_data = _fetch_filters(api_base, enabled_filter_ids)

    # ── 3. Widgets metadata (for grid skeleton rendering) ────
    widgets_data = layout_data.get("widgets", []) if layout_data else []
    _enrich_widgets(widgets_data)

    # ── 4. Build the dashboard data endpoint URL ─────────────
    dashboard_api_url = f"{api_base}/api/v1/dashboard/data"

    return render_template(
        "dashboard/index.html",
        user=user,
        api_base_url=api_base,
        dashboard_api_url=dashboard_api_url,
        filters=filters_data,
        widgets=widgets_data,
        layout=layout_data,
        tenant_id=tenant_id,
        role=role,
        grid_columns=GRID_COLUMNS,
        show_oee_tab=SHOW_OEE_TAB,
        access_token=session.get("access_token", ""),
    )


# ── Internal helpers ─────────────────────────────────────────────

def _fetch_layout(api_base: str, tenant_id, role: str):
    """Load layout config from the FastAPI layout endpoint."""
    try:
        url = (
            f"{api_base}/api/v1/layout/config"
            f"?tenant_id={tenant_id}&role={role}"
        )
        resp = httpx.get(url, timeout=10.0, follow_redirects=True)
        if resp.status_code == 200:
            data = resp.json()
            logger.info(
                f"[DASHBOARD] Layout loaded: "
                f"{len(data.get('enabled_widget_ids', []))} widgets, "
                f"{len(data.get('enabled_filter_ids', []))} filters"
            )
            return data
        logger.warning(f"[DASHBOARD] Layout API returned {resp.status_code}")
    except Exception as exc:
        logger.error(f"[DASHBOARD] Failed to load layout: {exc}")
    return None


def _fetch_filters(api_base: str, filter_ids: list):
    """Load resolved filters from the FastAPI filters endpoint."""
    try:
        url = f"{api_base}/api/v1/filters/"
        if filter_ids:
            ids_param = ",".join(str(i) for i in filter_ids)
            url += f"?filter_ids={ids_param}"
        resp = httpx.get(url, timeout=10.0, follow_redirects=True)
        if resp.status_code == 200:
            data = resp.json()
            logger.info(f"[DASHBOARD] Loaded {len(data)} filters")
            return data
        logger.warning(f"[DASHBOARD] Filters API returned {resp.status_code}")
    except Exception as exc:
        logger.error(f"[DASHBOARD] Failed to load filters: {exc}")
    return []


def _enrich_widgets(widgets_data: list):
    """
    Add frontend rendering metadata to each widget dict.

    Render behavior  → read from widget class attributes (auto-discovery).
    Layout positions → read from WIDGET_LAYOUT.
    Mutates ``widgets_data`` in place.
    """
    for idx, w in enumerate(widgets_data):
        if not isinstance(w, dict):
            continue
        class_name = w.get("widget_name", "")

        # Behavior: resolve class and read its class attributes
        cls = widget_engine._resolve_class(class_name)
        w["render_type"]  = cls.render       if cls else "unknown"
        w["chart_type"]   = cls.chart_type   if cls else ""
        w["chart_height"] = cls.chart_height if cls else "250px"

        # Layout: read from WIDGET_LAYOUT
        layout = WIDGET_LAYOUT.get(class_name, {})
        w["tab"]          = layout.get("tab", "produccion")
        w["order"]        = layout.get("order", idx)
        w["downtime_only"]= layout.get("downtime_only", False)

        # Build CSS Grid placement style
        col_span = layout.get("col_span", 1)
        row_span = layout.get("row_span", 1)
        w["col_span"] = col_span          # exposed for Jinja2 --col-span CSS var
        w["row_span"] = row_span          # exposed for Jinja2 --row-span CSS var
        parts = []
        if col_span > 1:
            parts.append(f"grid-column:span {col_span}")
        if row_span > 1:
            parts.append(f"grid-row:span {row_span}")
        parts.append(f"order:{w['order']}")
        w["grid_style"] = ";".join(parts)
