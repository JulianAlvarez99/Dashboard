"""
Widgets API Endpoints
Provides widget data and HTML rendering for the dashboard
"""

from datetime import date, datetime
from typing import Dict, List, Any, Optional

from fastapi import APIRouter, HTTPException, Query, Depends, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_tenant_db
from app.core.cache import metadata_cache
from app.services.widgets.widget_renderer import WidgetRenderer, FilterParams


router = APIRouter()


# === Pydantic Models ===

class WidgetDataResponse(BaseModel):
    """Widget data response"""
    widget_id: int
    widget_name: str
    widget_type: str
    data: Any
    metadata: Dict[str, Any]


class WidgetCatalogItem(BaseModel):
    """Widget catalog item"""
    widget_id: int
    widget_name: str
    description: str


# === Endpoints ===

@router.get("/catalog", response_model=List[WidgetCatalogItem])
async def get_widget_catalog():
    """
    Get all available widgets from catalog.
    
    Returns the full widget catalog loaded from cache.
    """
    catalog = metadata_cache.get_widget_catalog()
    return [
        WidgetCatalogItem(
            widget_id=wid,
            widget_name=data["widget_name"],
            description=data["description"]
        )
        for wid, data in catalog.items()
    ]


@router.get("/catalog/{widget_id}", response_model=WidgetCatalogItem)
async def get_widget_info(widget_id: int):
    """
    Get information about a specific widget.
    """
    widget = metadata_cache.get_widget(widget_id)
    if not widget:
        raise HTTPException(status_code=404, detail=f"Widget {widget_id} not found")
    
    return WidgetCatalogItem(
        widget_id=widget_id,
        widget_name=widget["widget_name"],
        description=widget["description"]
    )


@router.get("/{widget_id}/data", response_model=WidgetDataResponse)
async def get_widget_data(
    widget_id: int,
    line_id: Optional[int] = Query(None, description="Production line ID"),
    line_ids: Optional[str] = Query(None, description="Comma-separated line IDs for multi-line"),
    area_ids: Optional[str] = Query(None, description="Comma-separated area IDs"),
    product_ids: Optional[str] = Query(None, description="Comma-separated product IDs"),
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    shift_id: Optional[int] = Query(None, description="Shift ID"),
    interval: str = Query("hour", description="Time interval: minute, hour, day, week, month"),
    session: AsyncSession = Depends(get_tenant_db)
):
    """
    Get data for a specific widget with filter parameters.
    
    This endpoint returns JSON data that can be used to render charts.
    """
    # Check widget exists
    widget = metadata_cache.get_widget(widget_id)
    if not widget:
        raise HTTPException(status_code=404, detail=f"Widget {widget_id} not found")
    
    # Parse comma-separated IDs
    parsed_line_ids = None
    if line_ids:
        try:
            parsed_line_ids = [int(x.strip()) for x in line_ids.split(",")]
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid line_ids format")
    
    parsed_area_ids = None
    if area_ids:
        try:
            parsed_area_ids = [int(x.strip()) for x in area_ids.split(",")]
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid area_ids format")
    
    parsed_product_ids = None
    if product_ids:
        try:
            parsed_product_ids = [int(x.strip()) for x in product_ids.split(",")]
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid product_ids format")
    
    # Build filter params
    params = FilterParams(
        line_id=line_id,
        line_ids=parsed_line_ids,
        area_ids=parsed_area_ids,
        product_ids=parsed_product_ids,
        start_date=start_date,
        end_date=end_date,
        shift_id=shift_id,
        interval=interval
    )
    
    # Render widget
    renderer = WidgetRenderer(session)
    widget_data = await renderer.render(widget_id, params)
    
    if widget_data is None:
        raise HTTPException(status_code=404, detail=f"Widget {widget_id} not found or error rendering")
    
    return WidgetDataResponse(**widget_data.to_dict())


@router.get("/{widget_id}/render", response_class=HTMLResponse)
async def render_widget_html(
    request: Request,
    widget_id: int,
    line_id: Optional[int] = Query(None),
    line_ids: Optional[str] = Query(None),
    area_ids: Optional[str] = Query(None),
    product_ids: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    shift_id: Optional[int] = Query(None),
    interval: str = Query("hour"),
    session: AsyncSession = Depends(get_tenant_db)
):
    """
    Render widget as HTML partial for HTMX.
    
    This endpoint returns an HTML snippet that can be swapped into the dashboard.
    """
    # Check widget exists
    widget = metadata_cache.get_widget(widget_id)
    if not widget:
        return HTMLResponse(
            content=f'<div class="widget-error">Widget {widget_id} no encontrado</div>',
            status_code=404
        )
    
    # Parse IDs
    parsed_line_ids = [int(x.strip()) for x in line_ids.split(",")] if line_ids else None
    parsed_area_ids = [int(x.strip()) for x in area_ids.split(",")] if area_ids else None
    parsed_product_ids = [int(x.strip()) for x in product_ids.split(",")] if product_ids else None
    
    params = FilterParams(
        line_id=line_id,
        line_ids=parsed_line_ids,
        area_ids=parsed_area_ids,
        product_ids=parsed_product_ids,
        start_date=start_date,
        end_date=end_date,
        shift_id=shift_id,
        interval=interval
    )
    
    renderer = WidgetRenderer(session)
    widget_data = await renderer.render(widget_id, params)
    
    if widget_data is None:
        return HTMLResponse(
            content=f'<div class="widget-error">Error al renderizar widget</div>',
            status_code=500
        )
    
    # Generate HTML based on widget type
    html = _generate_widget_html(widget_data)
    
    return HTMLResponse(content=html)


def _generate_widget_html(widget_data) -> str:
    """
    Generate HTML for a widget based on its type.
    This is a simple implementation - in production, use Jinja2 templates.
    """
    wtype = widget_data.widget_type
    data = widget_data.data
    name = widget_data.widget_name
    
    # KPI Cards
    if wtype.startswith("kpi_"):
        value = data.get("value", 0)
        unit = data.get("unit", "")
        return f'''
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
            <h3 class="text-sm font-medium text-gray-500 dark:text-gray-400">{name}</h3>
            <p class="mt-2 text-3xl font-bold text-gray-900 dark:text-white">
                {value:,} <span class="text-lg font-normal text-gray-500">{unit}</span>
            </p>
        </div>
        '''
    
    # Line Chart
    elif wtype == "line_chart":
        chart_id = f"chart-{widget_data.widget_id}"
        labels = data.get("labels", [])
        datasets = data.get("datasets", [])
        return f'''
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
            <h3 class="text-sm font-medium text-gray-500 dark:text-gray-400 mb-4">{name}</h3>
            <canvas id="{chart_id}" height="200"></canvas>
            <script>
                new Chart(document.getElementById('{chart_id}'), {{
                    type: 'line',
                    data: {{
                        labels: {labels},
                        datasets: [{{{datasets[0] if datasets else {}}}}]
                    }},
                    options: {{
                        responsive: true,
                        plugins: {{ legend: {{ display: false }} }}
                    }}
                }});
            </script>
        </div>
        '''
    
    # Bar Chart
    elif wtype == "bar_chart":
        chart_id = f"chart-{widget_data.widget_id}"
        labels = data.get("labels", [])
        datasets = data.get("datasets", [])
        return f'''
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
            <h3 class="text-sm font-medium text-gray-500 dark:text-gray-400 mb-4">{name}</h3>
            <canvas id="{chart_id}" height="200"></canvas>
            <script>
                new Chart(document.getElementById('{chart_id}'), {{
                    type: 'bar',
                    data: {{
                        labels: {labels},
                        datasets: [{{{datasets[0] if datasets else {}}}}]
                    }},
                    options: {{ responsive: true }}
                }});
            </script>
        </div>
        '''
    
    # Pie Chart
    elif wtype == "pie_chart":
        chart_id = f"chart-{widget_data.widget_id}"
        labels = data.get("labels", [])
        datasets = data.get("datasets", [])
        return f'''
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
            <h3 class="text-sm font-medium text-gray-500 dark:text-gray-400 mb-4">{name}</h3>
            <canvas id="{chart_id}" height="200"></canvas>
            <script>
                new Chart(document.getElementById('{chart_id}'), {{
                    type: 'pie',
                    data: {{
                        labels: {labels},
                        datasets: [{{{datasets[0] if datasets else {}}}}]
                    }},
                    options: {{ responsive: true }}
                }});
            </script>
        </div>
        '''
    
    # Comparison Bar
    elif wtype == "comparison_bar":
        chart_id = f"chart-{widget_data.widget_id}"
        meta = widget_data.metadata
        return f'''
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
            <h3 class="text-sm font-medium text-gray-500 dark:text-gray-400 mb-4">{name}</h3>
            <div class="grid grid-cols-3 gap-4 text-center">
                <div>
                    <p class="text-2xl font-bold text-green-500">{meta.get("entrada", 0)}</p>
                    <p class="text-sm text-gray-500">Entrada</p>
                </div>
                <div>
                    <p class="text-2xl font-bold text-blue-500">{meta.get("salida", 0)}</p>
                    <p class="text-sm text-gray-500">Salida</p>
                </div>
                <div>
                    <p class="text-2xl font-bold text-red-500">{meta.get("descarte", 0)}</p>
                    <p class="text-sm text-gray-500">Descarte</p>
                </div>
            </div>
        </div>
        '''
    
    # Default
    return f'''
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <h3 class="text-sm font-medium text-gray-500 dark:text-gray-400">{name}</h3>
        <p class="text-gray-500 mt-2">Widget en desarrollo</p>
    </div>
    '''
