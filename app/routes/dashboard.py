"""
Dashboard Routes
Main dashboard page with dynamic filters and widgets

Layout loading strategy:
1. Primary: Load layout directly from DB + cache (no API dependency)
2. Fallback: Call FastAPI API if direct loading fails
This ensures the dashboard page renders even if FastAPI isn't running.
"""

import asyncio
import json
import os

from flask import Blueprint, render_template, request, session, redirect, url_for
import httpx

from app.core.config import settings
from app.routes.auth import login_required, get_current_user
from app.services.processors.helpers import infer_widget_type


dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")

# ── Load widget layout config once at import time ──
_WIDGET_LAYOUT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "static", "widget_layout.json"
)
_WIDGET_LAYOUT: dict = {}
_WIDGET_LAYOUT_SIZES: dict = {}

try:
    with open(_WIDGET_LAYOUT_PATH, "r", encoding="utf-8") as f:
        _raw = json.load(f)
    _WIDGET_LAYOUT = _raw.get("widgets", {})
    _WIDGET_LAYOUT_SIZES = _raw.get("size_css_classes", {})
except Exception as e:
    print(f"⚠️ Could not load widget_layout.json: {e}")


def _load_widget_layout():
    """Reload widget_layout.json from disk (allows hot-editing in debug mode)."""
    global _WIDGET_LAYOUT, _WIDGET_LAYOUT_SIZES
    try:
        with open(_WIDGET_LAYOUT_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        _WIDGET_LAYOUT = raw.get("widgets", {})
        _WIDGET_LAYOUT_SIZES = raw.get("size_css_classes", {})
    except Exception:
        pass  # keep whatever was loaded at import time


@dashboard_bp.route("/chart-test")
def chart_test():
    return render_template("chart_test.html")


@dashboard_bp.route("/")
@login_required
def index():
    """
    Main dashboard page.
    
    Loads layout configuration directly from the database/cache
    and renders the dashboard with:
    - Enabled filters based on layout_config from DASHBOARD_TEMPLATE
    - Enabled widgets based on layout_config from DASHBOARD_TEMPLATE
    - Alpine.js + Chart.js for client-side rendering
    """
    # Reload layout JSON so edits take effect without restart
    _load_widget_layout()

    user = get_current_user()
    tenant_id = user.get("tenant_id", 1)
    role = user.get("role", "ADMIN")
    
    # Extract tenant database name from user session
    tenant_info = user.get("tenant_info", {})
    tenant_config = tenant_info.get("config", {})
    db_name = tenant_config.get("db_name")
    
    if not db_name:
        return render_template(
            "dashboard/index.html",
            user=user,
            filters=[],
            widgets=[],
            api_base_url=settings.API_BASE_URL,
            error_message="Error: No se encontró el nombre de la base de datos del tenant",
            widget_layout=_WIDGET_LAYOUT,
            widget_layout_sizes=_WIDGET_LAYOUT_SIZES,
        )
    
    # Load layout DIRECTLY (no FastAPI dependency)
    layout_config = _get_layout_direct(tenant_id, role, db_name)
    
    if layout_config is None:
        # Fallback: try via API
        layout_config = _get_layout_from_api(tenant_id, role)
    
    if layout_config is None:
        filters = []
        widgets = []
        error_message = f"No hay configuración de layout para tenant {tenant_id} con rol {role}"
    else:
        filters = layout_config.get("filters", [])
        widgets = layout_config.get("widgets", [])
        error_message = None

    # Enrich each widget dict with its inferred type so the template
    # can look it up in widget_layout.json
    for w in widgets:
        if w and "widget_name" in w:
            w["widget_type_inferred"] = infer_widget_type(w["widget_name"])
    
    return render_template(
        "dashboard/index.html",
        user=user,
        filters=filters,
        widgets=widgets,
        api_base_url=settings.API_BASE_URL,
        error_message=error_message,
        widget_layout=_WIDGET_LAYOUT,
        widget_layout_sizes=_WIDGET_LAYOUT_SIZES,
    )


def _get_layout_direct(tenant_id: int, role: str, db_name: str):
    """
    Load layout configuration directly from DB + cache.
    Uses asyncio to call the async LayoutService from synchronous Flask.
    This avoids depending on FastAPI being up.
    
    Args:
        tenant_id: Tenant identifier
        role: User role (ADMIN, SUPERVISOR, etc.)
        db_name: Tenant database name (e.g., 'cliente_chacabuco')
    """
    try:
        from app.core.database import db_manager
        from app.core.cache import metadata_cache
        from app.services.config.layout_service import LayoutService

        async def _fetch():
            # Ensure cache is loaded with tenant-specific database
            if not metadata_cache.is_loaded:
                await metadata_cache.load_all(db_name)

            async with db_manager.get_global_session() as session:
                layout = await LayoutService.get_layout_config(
                    session, tenant_id, role
                )

            if layout is None:
                return None

            widgets = LayoutService.resolve_widgets_from_cache(layout.enabled_widget_ids)
            filters = LayoutService.resolve_filters_from_cache(layout.enabled_filter_ids)

            return {
                "tenant_id": layout.tenant_id,
                "role": layout.role,
                "widgets": [w.to_dict() for w in widgets],
                "filters": [f.to_dict() for f in filters],
                "raw_config": layout.raw_config
            }

        # Run the async function from sync Flask context
        return asyncio.run(_fetch())

    except Exception as e:
        print(f"⚠️ Direct layout loading failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def _get_layout_from_api(tenant_id: int, role: str):
    """
    Fallback: Get layout configuration from FastAPI endpoint.
    Only used if direct loading fails.
    """
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(
                f"{settings.API_BASE_URL}/api/v1/layout/config",
                params={"tenant_id": tenant_id, "role": role}
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                return None
            else:
                print(f"Error fetching layout: {response.status_code} - {response.text}")
                return None
                
    except httpx.RequestError as e:
        print(f"⚠️ API not reachable: {e}")
        return None


@dashboard_bp.route("/widget/<int:widget_id>")
@login_required
def widget_partial(widget_id: int):
    """
    Render a single widget partial via HTMX.
    Proxies to FastAPI widget render endpoint.
    """
    # Get filter params from query string
    params = request.args.to_dict()
    
    try:
        # Call FastAPI to get widget HTML
        with httpx.Client() as client:
            response = client.get(
                f"{settings.API_BASE_URL}/api/v1/widgets/{widget_id}/render",
                params=params,
                timeout=10.0
            )
            return response.text
    except Exception as e:
        return f'<div class="widget-error">Error cargando widget: {str(e)}</div>'
