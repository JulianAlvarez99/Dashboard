"""
Dashboard routes — Renders the filter panel and widget grid.

After login the user lands here. The route:
1. Loads ``layout_config`` from ``dashboard_template`` for the user's
   tenant + role to determine which widgets and filters are enabled.
2. Passes only the enabled filters (via ``filter_ids``) and widgets
   to the template for rendering.
"""

import httpx

from flask import Blueprint, render_template, session

from new_app.routes.auth import login_required, get_current_user
from new_app.core.config import get_settings

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


@dashboard_bp.route("/")
@login_required
def index():
    user = get_current_user()
    settings = get_settings()
    api_base = settings.API_BASE_URL

    tenant_id = user.get("tenant_id")
    role = user.get("role", "ADMIN")

    # ── 1. Load layout config (widget + filter IDs) ──────────
    layout_data = None
    try:
        layout_url = (
            f"{api_base}/api/v1/layout/config"
            f"?tenant_id={tenant_id}&role={role}"
        )
        resp = httpx.get(layout_url, timeout=10.0, follow_redirects=True)
        if resp.status_code == 200:
            layout_data = resp.json()
            print(
                f"[DASHBOARD] Layout loaded: "
                f"{len(layout_data.get('enabled_widget_ids', []))} widgets, "
                f"{len(layout_data.get('enabled_filter_ids', []))} filters"
            )
        else:
            print(f"[DASHBOARD] Layout API returned {resp.status_code}: {resp.text}")
    except Exception as exc:
        print(f"[DASHBOARD] Failed to load layout: {exc}")

    # ── 2. Fetch only the enabled filters ────────────────────
    enabled_filter_ids = (
        layout_data.get("enabled_filter_ids", [])
        if layout_data
        else []
    )
    filters_data = []
    try:
        filters_url = f"{api_base}/api/v1/filters/"
        if enabled_filter_ids:
            ids_param = ",".join(str(i) for i in enabled_filter_ids)
            filters_url += f"?filter_ids={ids_param}"
        resp = httpx.get(filters_url, timeout=10.0, follow_redirects=True)
        if resp.status_code == 200:
            filters_data = resp.json()
            print(f"[DASHBOARD] Loaded {len(filters_data)} filters")
        else:
            print(f"[DASHBOARD] Filters API returned {resp.status_code}")
    except Exception as exc:
        print(f"[DASHBOARD] Failed to load filters: {exc}")

    # ── 3. Widgets metadata (for future grid rendering) ──────
    widgets_data = layout_data.get("widgets", []) if layout_data else []

    return render_template(
        "dashboard/index.html",
        user=user,
        api_base_url=api_base,
        filters=filters_data,
        widgets=widgets_data,
        layout=layout_data,
    )
