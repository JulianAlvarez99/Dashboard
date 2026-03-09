"""
Dashboard route — Flask Blueprint.

Phase 3: Renders filters and widgets from cache + engines.
"""

import logging

from flask import Blueprint, render_template

from dashboard_saas.core.cache import metadata_cache
from dashboard_saas.core.config import settings
from dashboard_saas.services.filters.engine import FilterEngine
from dashboard_saas.services.widgets.engine import WidgetEngine

logger = logging.getLogger(__name__)

# Blueprint: all routes under /dashboard/
dashboard_bp = Blueprint(
    "dashboard",
    __name__,
    url_prefix="/dashboard",
)


@dashboard_bp.route("/")
def index():
    """
    Render the dashboard page.

    Passes filter and widget data to the template so the frontend
    can render controls dynamically.
    """
    # Use singletons instead of instantiating engines on every request
    from dashboard_saas.services.filters.engine import filter_engine
    from dashboard_saas.services.widgets.engine import widget_engine

    return render_template(
        "dashboard/index.html",
        # Server → template data
        api_base_url=settings.API_BASE_URL,
        filters=filter_engine.get_all_serialized(),
        widgets=widget_engine.get_all_serialized(),
    )
