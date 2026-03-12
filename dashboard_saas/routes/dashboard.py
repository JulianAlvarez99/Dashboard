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

    PASO 3: Cargando la UI del Dashboard (Flask)
    Cuando abres la aplicación en el navegador web, este Blueprint atiende
    la primera solicitud "/" puramente HTML.
    """
    
    # PASO 3.1: Rendimiento Máximo (Milisegundos)
    # Como ya instanciamos los motores (Singletons) tras arrancar el servidor 
    # y ya procesaron todas sus configuraciones, esto NO requiere consultar base de datos, 
    # NO lee la red, ni instancia ninguna clase nueva, sólo accede a sus objetos en RAM.
    from dashboard_saas.services.filters.engine import filter_engine
    from dashboard_saas.services.widgets.engine import widget_engine
    from dashboard_saas.services.layout_service import layout_service

    # Obtenemos la configuracion de layout_config desde la tabla dashboard_template
    # Fase 1: hardcoded para el DEFAULT_TENANT_ID cargado en las variables de entorno, rol ADMIN 
    layout_config = layout_service.get_layout_config(settings.DEFAULT_TENANT_ID, "ADMIN")

    all_filters = filter_engine.get_all_serialized()
    all_widgets = widget_engine.get_all_serialized()

    if layout_config:
        allowed_filters = set(layout_config.get("filters", []))
        allowed_widgets = set(layout_config.get("widgets", []))
        
        enabled_filters = [f for f in all_filters if f.get("filter_id") in allowed_filters]
        enabled_widgets = [w for w in all_widgets if w.get("widget_id") in allowed_widgets]
    else:
        # En caso de no existir o fallar, cargamos todos a modo de fallback
        enabled_filters = all_filters
        enabled_widgets = all_widgets

    # PASO 3.2: Renderizado hacia la Interfaz (Jinja2)
    # Le mandamos el método get_all_serialized(). Este método simplemente junta todos 
    # los atributos de la clase de Python del filtro junto con sus opciones, los pasa
    # a formato Diccionario Nativo dict() de Python, y se los entrega al motor `render_template`.
    # Allí (en el index.html), Alpine JS convertirá el HTML + Jinja2 en un json funcional para frontend.
    return render_template(
        "dashboard/index.html",
        # Server → template data
        api_base_url=settings.API_BASE_URL,
        filters=enabled_filters,
        widgets=enabled_widgets,
    )
