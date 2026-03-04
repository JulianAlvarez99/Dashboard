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
from new_app.config.widget_layout    import GRID_COLUMNS, SHOW_OEE_TAB
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

    # ── 2b. Collect js_inline handlers from filter data ──────
    inline_js_blocks = []
    seen_handlers: set = set()
    for flt in filters_data:
        block = flt.get("js_inline") or ""
        block = block.strip()
        if block and block not in seen_handlers:
            inline_js_blocks.append(block)
            seen_handlers.add(block)
    filter_inline_js = ",\n".join(inline_js_blocks)

    # ── 3. Widgets metadata (for grid skeleton rendering) ────
    widgets_data = layout_data.get("widgets", []) if layout_data else []
    _enrich_widgets(widgets_data)

    # ── 3b. Collect js_inline blocks from widget classes ─────
    widget_names = [w["widget_name"] for w in widgets_data if isinstance(w, dict)]
    widget_inline_js = widget_engine.get_js_inline_blocks(widget_names)

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
        filter_inline_js=filter_inline_js,
        widget_inline_js=widget_inline_js,
    )


# ── Internal helpers ─────────────────────────────────────────────

def _fetch_layout(api_base: str, tenant_id, role: str):
    """Load layout config from the FastAPI layout endpoint.

    Retries up to 3 times with 2-second gaps so a briefly-unavailable
    FastAPI (e.g. slow cold-start) does not break the first page load.
    """
    import time
    url = (
        f"{api_base}/api/v1/layout/config"
        f"?tenant_id={tenant_id}&role={role}"
    )
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            resp = httpx.get(url, timeout=10.0, follow_redirects=True)
            if resp.status_code == 200:
                data = resp.json()
                logger.info(
                    "[DASHBOARD] Layout loaded: %d widgets, %d filters",
                    len(data.get("enabled_widget_ids", [])),
                    len(data.get("enabled_filter_ids", [])),
                )
                return data
            logger.warning(
                "[DASHBOARD] Layout API returned %s (attempt %d/%d)",
                resp.status_code, attempt, max_retries,
            )
        except Exception as exc:
            logger.warning(
                "[DASHBOARD] Failed to load layout (attempt %d/%d): %s",
                attempt, max_retries, exc,
            )
        if attempt < max_retries:
            time.sleep(2)
    logger.error("[DASHBOARD] Could not load layout after %d attempts", max_retries)
    return None


def _fetch_filters(api_base: str, filter_ids: list):
    """Load resolved filters from the FastAPI filters endpoint.

    Retries up to 3 times with 2-second gaps.
    """
    import time
    url = f"{api_base}/api/v1/filters/"
    if filter_ids:
        url += f"?filter_ids={','.join(str(i) for i in filter_ids)}"
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            resp = httpx.get(url, timeout=10.0, follow_redirects=True)
            if resp.status_code == 200:
                data = resp.json()
                logger.info("[DASHBOARD] Loaded %d filters", len(data))
                return data
            logger.warning(
                "[DASHBOARD] Filters API returned %s (attempt %d/%d)",
                resp.status_code, attempt, max_retries,
            )
        except Exception as exc:
            logger.warning(
                "[DASHBOARD] Failed to load filters (attempt %d/%d): %s",
                attempt, max_retries, exc,
            )
        if attempt < max_retries:
            time.sleep(2)
    logger.error("[DASHBOARD] Could not load filters after %d attempts", max_retries)
    return []


def _enrich_widgets(widgets_data: list):
    """
    Add frontend rendering metadata to each widget dict.

    Reads layout from widget class attributes (via WidgetEngine).
    Mutates ``widgets_data`` in place.
    """
    for idx, w in enumerate(widgets_data):
        if not isinstance(w, dict):
            continue
        class_name = w.get("widget_name", "")

        # ── Read layout from widget class attributes ─────────
        cls = widget_engine.get_class(class_name)
        if cls is not None:
            layout = cls.get_layout()
        else:
            # Widget class not found — use empty defaults and log warning
            logger.warning("[Dashboard] Widget class not found: %s", class_name)
            layout = {}

        # Render metadata
        w["render_type"]  = layout.get("render", "kpi")
        w["chart_type"]   = layout.get("chart_type", "")
        w["chart_height"] = layout.get("chart_height", "250px")

        # Layout metadata
        w["tab"]           = layout.get("tab", "produccion")
        w["order"]         = layout.get("order", idx)
        w["downtime_only"] = layout.get("downtime_only", False)

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
