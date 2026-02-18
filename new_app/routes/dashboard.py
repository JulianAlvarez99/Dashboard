"""
Dashboard routes — Renders the filter panel and widget grid.

After login the user lands here. The route:
1. Loads ``layout_config`` from ``dashboard_template`` for the user's
   tenant + role to determine which widgets and filters are enabled.
2. Enriches each widget with frontend rendering metadata (partial type,
   grid size, chart_type) from ``WIDGET_RENDER_MAP``.
3. Passes only the enabled filters (via ``filter_ids``) and enriched
   widgets to the template for rendering.
4. The frontend JS sends filter submissions to ``POST /api/v1/dashboard/data``
   (the Etapa 6 orchestrator endpoint).
"""

import logging

import httpx

from flask import Blueprint, render_template, session

from new_app.routes.auth import login_required, get_current_user
from new_app.core.config import get_settings
from new_app.config.widget_registry import WIDGET_RENDER_MAP, WIDGET_SIZE_CSS

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

    Adds: render_type, chart_type, size_class, chart_height, downtime_only.
    Mutates ``widgets_data`` in place.
    """
    for idx, w in enumerate(widgets_data):
        if not isinstance(w, dict):
            continue
        class_name = w.get("widget_name", "")
        render_info = WIDGET_RENDER_MAP.get(class_name, {})
        w["render_type"] = render_info.get("render", "unknown")
        w["chart_type"] = render_info.get("chart_type", "")
        w["size_class"] = WIDGET_SIZE_CSS.get(
            render_info.get("size", "small"), "col-span-1"
        )
        w["chart_height"] = render_info.get("chart_height", "250px")
        w["downtime_only"] = render_info.get("downtime_only", False)
        w["order"] = idx
