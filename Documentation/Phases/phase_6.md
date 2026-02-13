# AGENTS.MD - FASE 6

## FASE 6: Motor de Widgets y Dashboard Templates

### 🎯 OBJETIVO DE LA FASE 6

Implementar el motor de widgets dinámico que interpreta la configuración de `WIDGET_CATALOG` y `DASHBOARD_TEMPLATE` para renderizar dashboards personalizados según el rol del usuario, sin código hardcoded por cliente.

**Duración Estimada:** 2 semanas  
**Prioridad:** Alta (funcionalidad core del dashboard)

**PRINCIPIO FUNDAMENTAL:** El sistema actúa como un "motor de reglas" que interpreta la configuración de la base de datos para renderizar widgets dinámicamente.

---

## 📦 TASK 6.1: Widget Service - Motor de Interpretación

**Descripción:**  
Crear el servicio que interpreta `WIDGET_CATALOG`, valida parámetros con JSON Schema y ejecuta la lógica correspondiente según el `widget_type`.

**Criterios de Aceptación:**
- ✅ Método `render_widget()` implementado con validación JSON Schema
- ✅ 6 tipos de widgets soportados (line_chart, pie_chart, bar_chart, kpi_card, table, comparison_bar)
- ✅ Routing dinámico según `widget_type`
- ✅ Integración con `detection_service` y `metrics_service`
- ✅ Formato de salida compatible con Chart.js
- ✅ Manejo de errores robusto

**Archivo:** `app/services/widget_service.py`

```python
"""
Widget Service - Motor de interpretación de WIDGET_CATALOG
"""
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jsonschema import validate, ValidationError as JSONSchemaValidationError
import pandas as pd

from app.models.global_db.template import WidgetCatalog
from app.services.detection_service import DetectionService
from app.services.metrics_service import MetricsService
from app.services.downtime_service import DowntimeService
from app.core.cache import MetadataCache
from app.schemas.query import QueryFilters


class WidgetService:
    """
    Servicio para renderizar widgets dinámicamente según WIDGET_CATALOG
    
    Principio: Configuration over Code
    - Lee widget_type de WIDGET_CATALOG
    - Valida params con required_params (JSON Schema)
    - Ejecuta renderer correspondiente
    - Retorna datos formateados para Chart.js
    """
    
    def __init__(self, cache: MetadataCache, db: AsyncSession):
        self.cache = cache
        self.db = db
        self.detection_service = DetectionService(cache, db)
        self.metrics_service = MetricsService(cache, db)
        self.downtime_service = DowntimeService(cache, db)
    
    async def render_widget(
        self,
        widget_id: int,
        params: Dict[str, Any],
        tenant_id: int
    ) -> Dict[str, Any]:
        """
        Renderiza un widget según su configuración en WIDGET_CATALOG
        
        Args:
            widget_id: ID del widget en WIDGET_CATALOG
            params: Parámetros del widget (filtros, configuración)
            tenant_id: ID del tenant (para validación)
        
        Returns:
            Dict con estructura:
            {
                'widget_id': int,
                'widget_name': str,
                'widget_type': str,
                'data': Dict  # Formato específico según widget_type
            }
        
        Raises:
            ValueError: Si widget no existe o parámetros inválidos
        """
        # 1. Obtener configuración del widget de WIDGET_CATALOG
        widget_config = await self._get_widget_config(widget_id)
        
        if not widget_config:
            raise ValueError(f"Widget {widget_id} not found in catalog")
        
        # 2. Validar parámetros contra JSON Schema
        try:
            validate(instance=params, schema=widget_config['required_params'])
        except JSONSchemaValidationError as e:
            raise ValueError(f"Invalid widget parameters: {e.message}")
        
        # 3. Routing dinámico según widget_type
        widget_renderers = {
            'line_chart': self._render_line_chart,
            'bar_chart': self._render_bar_chart,
            'pie_chart': self._render_pie_chart,
            'kpi_card': self._render_kpi_card,
            'table': self._render_table,
            'comparison_bar': self._render_comparison_bar
        }
        
        renderer = widget_renderers.get(widget_config['widget_type'])
        
        if not renderer:
            raise ValueError(f"Unknown widget type: {widget_config['widget_type']}")
        
        # 4. Ejecutar renderer
        data = await renderer(params)
        
        # 5. Retornar estructura completa
        return {
            'widget_id': widget_id,
            'widget_name': widget_config['widget_name'],
            'widget_type': widget_config['widget_type'],
            'data': data
        }
    
    async def _get_widget_config(self, widget_id: int) -> Dict:
        """Obtiene configuración del widget de DB_GLOBAL"""
        result = await self.db.execute(
            select(WidgetCatalog).where(WidgetCatalog.widget_id == widget_id)
        )
        widget = result.scalar_one_or_none()
        
        if not widget:
            return None
        
        return {
            'widget_name': widget.widget_name,
            'widget_type': widget.widget_type,
            'description': widget.description,
            'required_params': widget.required_params,
            'visibility_rules': widget.visibility_rules
        }
    
    async def _render_line_chart(self, params: Dict) -> Dict:
        """
        Renderiza gráfico de línea de producción por tiempo
        
        Formato de salida (Chart.js Line Chart):
        {
            'labels': ['2024-01-01 08:00', '2024-01-01 08:15', ...],
            'datasets': [{
                'label': 'Producción',
                'data': [120, 135, 142, ...],
                'borderColor': 'rgb(59, 130, 246)',
                'backgroundColor': 'rgba(59, 130, 246, 0.1)',
                'tension': 0.4,
                'fill': True
            }]
        }
        """
        # Construir filtros
        filters = QueryFilters(**params)
        
        # Obtener detecciones
        df = await self.detection_service.get_enriched_detections(filters)
        
        if df.empty:
            return {
                'labels': [],
                'datasets': [{
                    'label': 'Producción',
                    'data': [],
                    'borderColor': 'rgb(59, 130, 246)',
                    'backgroundColor': 'rgba(59, 130, 246, 0.1)'
                }]
            }
        
        # Agrupar por intervalo
        interval = params.get('interval', '15min')
        aggregated = await self.metrics_service.aggregate_by_interval(df, interval)
        
        # Formatear para Chart.js
        return {
            'labels': aggregated['detected_at'].dt.strftime('%Y-%m-%d %H:%M').tolist(),
            'datasets': [{
                'label': 'Producción (unidades)',
                'data': aggregated['count'].tolist(),
                'borderColor': 'rgb(59, 130, 246)',
                'backgroundColor': 'rgba(59, 130, 246, 0.1)',
                'tension': 0.4,
                'fill': True,
                'borderWidth': 2
            }]
        }
    
    async def _render_pie_chart(self, params: Dict) -> Dict:
        """
        Renderiza gráfico de torta de distribución de productos
        
        Formato de salida (Chart.js Pie Chart):
        {
            'labels': ['Producto A', 'Producto B', 'Producto C'],
            'datasets': [{
                'data': [45, 30, 25],
                'backgroundColor': ['rgb(59, 130, 246)', 'rgb(16, 185, 129)', ...]
            }]
        }
        """
        filters = QueryFilters(**params)
        df = await self.detection_service.get_enriched_detections(filters)
        
        if df.empty:
            return {
                'labels': [],
                'datasets': [{'data': [], 'backgroundColor': []}]
            }
        
        # Agrupar por producto
        product_dist = df.groupby('product_name').size().sort_values(ascending=False)
        
        # Colores predefinidos
        colors = [
            'rgb(59, 130, 246)',   # Blue
            'rgb(16, 185, 129)',   # Green
            'rgb(249, 115, 22)',   # Orange
            'rgb(139, 92, 246)',   # Purple
            'rgb(236, 72, 153)',   # Pink
            'rgb(234, 179, 8)',    # Yellow
            'rgb(239, 68, 68)',    # Red
        ]
        
        return {
            'labels': product_dist.index.tolist(),
            'datasets': [{
                'data': product_dist.values.tolist(),
                'backgroundColor': colors[:len(product_dist)],
                'borderWidth': 2,
                'borderColor': '#fff'
            }]
        }
    
    async def _render_bar_chart(self, params: Dict) -> Dict:
        """
        Renderiza gráfico de barras genérico
        """
        filters = QueryFilters(**params)
        df = await self.detection_service.get_enriched_detections(filters)
        
        if df.empty:
            return {
                'labels': [],
                'datasets': [{'label': 'Sin datos', 'data': [], 'backgroundColor': []}]
            }
        
        # Agrupar por área
        area_dist = df.groupby('area_name').size()
        
        return {
            'labels': area_dist.index.tolist(),
            'datasets': [{
                'label': 'Detecciones por Área',
                'data': area_dist.values.tolist(),
                'backgroundColor': 'rgba(59, 130, 246, 0.8)',
                'borderColor': 'rgb(59, 130, 246)',
                'borderWidth': 2
            }]
        }
    
    async def _render_comparison_bar(self, params: Dict) -> Dict:
        """
        Renderiza comparación Entrada vs Salida vs Descarte
        
        Formato de salida:
        {
            'labels': ['Entrada', 'Salida', 'Descarte'],
            'datasets': [{
                'label': 'Unidades',
                'data': [1000, 950, 50],
                'backgroundColor': ['green', 'blue', 'red']
            }]
        }
        """
        filters = QueryFilters(**params)
        line_id = params['line_id']
        
        # Obtener áreas de entrada y salida
        input_area = await self._get_input_area(line_id)
        output_area = await self._get_output_area(line_id)
        
        # Contar detecciones por área
        input_count = await self.detection_service.count_detections(
            line_id, input_area['area_id'],
            filters.start_date, filters.end_date
        )
        
        output_count = await self.detection_service.count_detections(
            line_id, output_area['area_id'],
            filters.start_date, filters.end_date
        )
        
        rejected = input_count - output_count if input_count > output_count else 0
        
        return {
            'labels': ['Entrada', 'Salida', 'Descarte'],
            'datasets': [{
                'label': 'Unidades',
                'data': [input_count, output_count, rejected],
                'backgroundColor': [
                    'rgba(16, 185, 129, 0.8)',   # Green
                    'rgba(59, 130, 246, 0.8)',   # Blue
                    'rgba(239, 68, 68, 0.8)'     # Red
                ],
                'borderColor': [
                    'rgb(16, 185, 129)',
                    'rgb(59, 130, 246)',
                    'rgb(239, 68, 68)'
                ],
                'borderWidth': 2
            }]
        }
    
    async def _render_kpi_card(self, params: Dict) -> Dict:
        """
        Renderiza KPI individual
        
        Formato de salida:
        {
            'value': 85.5,
            'unit': '%',
            'label': 'OEE',
            'trend': 'up',  # 'up', 'down', 'stable'
            'change': 2.3   # Cambio porcentual
        }
        """
        kpi_type = params.get('kpi_type')
        filters = QueryFilters(**params)
        
        if kpi_type == 'oee':
            metrics = await self.metrics_service.calculate_oee(
                filters.line_id, filters.start_date, filters.end_date
            )
            return {
                'value': round(metrics['oee'], 2),
                'unit': '%',
                'label': 'OEE',
                'subtitle': 'Overall Equipment Effectiveness'
            }
        
        elif kpi_type == 'total_production':
            df = await self.detection_service.get_enriched_detections(filters)
            return {
                'value': len(df),
                'unit': 'unidades',
                'label': 'Producción Total',
                'subtitle': 'Período seleccionado'
            }
        
        elif kpi_type == 'total_weight':
            df = await self.detection_service.get_enriched_detections(filters)
            total_weight = await self.metrics_service.calculate_total_weight(df)
            return {
                'value': round(total_weight, 2),
                'unit': 'kg',
                'label': 'Peso Total',
                'subtitle': 'Producción acumulada'
            }
        
        elif kpi_type == 'downtime_count':
            downtimes = await self.downtime_service.get_downtimes(
                filters.line_id, filters.start_date, filters.end_date
            )
            return {
                'value': len(downtimes),
                'unit': 'paradas',
                'label': 'Total de Paradas',
                'subtitle': 'Eventos registrados'
            }
        
        elif kpi_type == 'availability':
            metrics = await self.metrics_service.calculate_oee(
                filters.line_id, filters.start_date, filters.end_date
            )
            return {
                'value': round(metrics['availability'], 2),
                'unit': '%',
                'label': 'Disponibilidad',
                'subtitle': 'Tiempo operativo'
            }
        
        elif kpi_type == 'performance':
            metrics = await self.metrics_service.calculate_oee(
                filters.line_id, filters.start_date, filters.end_date
            )
            return {
                'value': round(metrics['performance'], 2),
                'unit': '%',
                'label': 'Rendimiento',
                'subtitle': 'Producción vs objetivo'
            }
        
        elif kpi_type == 'quality':
            metrics = await self.metrics_service.calculate_oee(
                filters.line_id, filters.start_date, filters.end_date
            )
            return {
                'value': round(metrics['quality'], 2),
                'unit': '%',
                'label': 'Calidad',
                'subtitle': 'Productos conformes'
            }
        
        else:
            raise ValueError(f"Unknown KPI type: {kpi_type}")
    
    async def _render_table(self, params: Dict) -> Dict:
        """
        Renderiza tabla de paradas
        
        Formato de salida:
        {
            'columns': ['Inicio', 'Fin', 'Duración', 'Razón'],
            'rows': [
                {'start_time': '...', 'end_time': '...', 'duration': '...', 'reason': '...'},
                ...
            ]
        }
        """
        filters = QueryFilters(**params)
        
        downtimes = await self.downtime_service.get_downtimes(
            filters.line_id, filters.start_date, filters.end_date
        )
        
        # Formatear filas
        rows = []
        for dt in downtimes:
            rows.append({
                'start_time': dt['start_time'].strftime('%Y-%m-%d %H:%M:%S'),
                'end_time': dt['end_time'].strftime('%Y-%m-%d %H:%M:%S'),
                'duration': self._format_duration(dt['duration']),
                'reason': dt.get('reason', 'Sin especificar')
            })
        
        return {
            'columns': ['Inicio', 'Fin', 'Duración', 'Razón'],
            'rows': rows
        }
    
    def _format_duration(self, seconds: float) -> str:
        """Formatea duración en formato HH:MM:SS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    async def _get_input_area(self, line_id: int) -> Dict:
        """Obtiene área de entrada de la línea (area_order = 1)"""
        areas = self.cache.get_all_areas()
        for area in areas.values():
            if area['line_id'] == line_id and area['area_order'] == 1:
                return area
        raise ValueError(f"Input area not found for line {line_id}")
    
    async def _get_output_area(self, line_id: int) -> Dict:
        """Obtiene área de salida de la línea (area_order máximo)"""
        areas = self.cache.get_all_areas()
        line_areas = [a for a in areas.values() if a['line_id'] == line_id]
        if not line_areas:
            raise ValueError(f"No areas found for line {line_id}")
        return max(line_areas, key=lambda x: x['area_order'])
    
    async def get_all_widgets(self) -> List[Dict]:
        """
        Obtiene catálogo completo de widgets disponibles
        (Para configuración de dashboards por admins)
        """
        result = await self.db.execute(select(WidgetCatalog))
        widgets = result.scalars().all()
        
        return [
            {
                'widget_id': w.widget_id,
                'widget_name': w.widget_name,
                'widget_type': w.widget_type,
                'description': w.description,
                'required_params': w.required_params
            }
            for w in widgets
        ]
```

**Verificación:**

```bash
# Test manual del widget service
python scripts/test_widget_service.py
```

---

## 📦 TASK 6.2: Dashboard Template Service

**Descripción:**  
Implementar servicio que gestiona `DASHBOARD_TEMPLATE`, retornando el layout configurado según el rol del usuario.

**Criterios de Aceptación:**
- ✅ Método `get_dashboard_layout()` implementado
- ✅ Templates por defecto para roles (admin, viewer, manager)
- ✅ Soporte para templates personalizados por tenant
- ✅ Fallback a template por defecto si no existe personalizado

**Archivo:** `app/services/dashboard_service.py`

```python
"""
Dashboard Service - Gestión de templates y layouts
"""
from typing import Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.global_db.template import DashboardTemplate


class DashboardService:
    """
    Servicio para gestionar templates de dashboards
    
    Principio: Configuration over Code
    - Lee DASHBOARD_TEMPLATE según tenant_id y role
    - Retorna layout_config (JSON con grid de widgets)
    - Fallback a templates por defecto del sistema
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_dashboard_layout(
        self,
        tenant_id: int,
        role: str
    ) -> Dict:
        """
        Obtiene layout del dashboard según tenant y rol
        
        Args:
            tenant_id: ID del tenant
            role: Rol del usuario (admin, viewer, manager)
        
        Returns:
            Dict con estructura:
            {
                'grid': [
                    {'widget_id': 1, 'x': 0, 'y': 0, 'w': 8, 'h': 4},
                    {'widget_id': 2, 'x': 8, 'y': 0, 'w': 4, 'h': 2},
                    ...
                ]
            }
        """
        # Buscar template específico para el tenant y rol
        result = await self.db.execute(
            select(DashboardTemplate).where(
                and_(
                    DashboardTemplate.tenant_id == tenant_id,
                    DashboardTemplate.role_access == role
                )
            )
        )
        template = result.scalar_one_or_none()
        
        if template:
            return template.layout_config
        
        # Fallback a template por defecto del sistema
        return self._get_default_template(role)
    
    def _get_default_template(self, role: str) -> Dict:
        """
        Retorna template por defecto según rol
        
        Grid System:
        - 12 columnas
        - x, y: posición
        - w: ancho (1-12)
        - h: alto (unidades arbitrarias)
        """
        default_layouts = {
            'admin': {
                'grid': [
                    # Fila 1: Gráfico de línea grande
                    {'widget_id': 1, 'x': 0, 'y': 0, 'w': 8, 'h': 4, 'params': {'widget_type': 'line_chart'}},
                    
                    # Fila 1: KPIs a la derecha
                    {'widget_id': 2, 'x': 8, 'y': 0, 'w': 4, 'h': 2, 'params': {'kpi_type': 'oee'}},
                    {'widget_id': 3, 'x': 8, 'y': 2, 'w': 4, 'h': 2, 'params': {'kpi_type': 'total_production'}},
                    
                    # Fila 2: Comparación y distribución
                    {'widget_id': 4, 'x': 0, 'y': 4, 'w': 6, 'h': 4, 'params': {'widget_type': 'comparison_bar'}},
                    {'widget_id': 5, 'x': 6, 'y': 4, 'w': 6, 'h': 4, 'params': {'widget_type': 'pie_chart'}},
                    
                    # Fila 3: Tabla de paradas
                    {'widget_id': 6, 'x': 0, 'y': 8, 'w': 12, 'h': 4, 'params': {'widget_type': 'table'}},
                    
                    # Fila 4: KPIs adicionales
                    {'widget_id': 7, 'x': 0, 'y': 12, 'w': 4, 'h': 2, 'params': {'kpi_type': 'availability'}},
                    {'widget_id': 8, 'x': 4, 'y': 12, 'w': 4, 'h': 2, 'params': {'kpi_type': 'performance'}},
                    {'widget_id': 9, 'x': 8, 'y': 12, 'w': 4, 'h': 2, 'params': {'kpi_type': 'quality'}},
                ]
            },
            'viewer': {
                'grid': [
                    # Vista simplificada para viewers
                    {'widget_id': 1, 'x': 0, 'y': 0, 'w': 12, 'h': 4, 'params': {'widget_type': 'line_chart'}},
                    {'widget_id': 2, 'x': 0, 'y': 4, 'w': 6, 'h': 3, 'params': {'kpi_type': 'oee'}},
                    {'widget_id': 5, 'x': 6, 'y': 4, 'w': 6, 'h': 4, 'params': {'widget_type': 'pie_chart'}},
                ]
            },
            'manager': {
                'grid': [
                    # Vista intermedia para managers
                    {'widget_id': 1, 'x': 0, 'y': 0, 'w': 8, 'h': 4, 'params': {'widget_type': 'line_chart'}},
                    {'widget_id': 2, 'x': 8, 'y': 0, 'w': 4, 'h': 2, 'params': {'kpi_type': 'oee'}},
                    {'widget_id': 3, 'x': 8, 'y': 2, 'w': 4, 'h': 2, 'params': {'kpi_type': 'total_production'}},
                    {'widget_id': 4, 'x': 0, 'y': 4, 'w': 6, 'h': 4, 'params': {'widget_type': 'comparison_bar'}},
                    {'widget_id': 5, 'x': 6, 'y': 4, 'w': 6, 'h': 4, 'params': {'widget_type': 'pie_chart'}},
                    {'widget_id': 6, 'x': 0, 'y': 8, 'w': 12, 'h': 4, 'params': {'widget_type': 'table'}},
                ]
            }
        }
        
        return default_layouts.get(role, default_layouts['viewer'])
    
    async def save_custom_template(
        self,
        tenant_id: int,
        role: str,
        layout_config: Dict
    ) -> DashboardTemplate:
        """
        Guarda template personalizado para un tenant
        
        Args:
            tenant_id: ID del tenant
            role: Rol objetivo
            layout_config: Configuración del grid
        
        Returns:
            DashboardTemplate creado/actualizado
        """
        # Buscar si ya existe
        result = await self.db.execute(
            select(DashboardTemplate).where(
                and_(
                    DashboardTemplate.tenant_id == tenant_id,
                    DashboardTemplate.role_access == role
                )
            )
        )
        template = result.scalar_one_or_none()
        
        if template:
            # Actualizar existente
            template.layout_config = layout_config
        else:
            # Crear nuevo
            template = DashboardTemplate(
                tenant_id=tenant_id,
                role_access=role,
                layout_config=layout_config
            )
            self.db.add(template)
        
        await self.db.commit()
        await self.db.refresh(template)
        
        return template
```

---

## 📦 TASK 6.3: API Endpoints para Widgets y Dashboard

**Descripción:**  
Crear endpoints REST para obtener layouts, renderizar widgets y gestionar templates.

**Criterios de Aceptación:**
- ✅ `GET /api/v1/dashboard/layout` - Obtiene layout según rol
- ✅ `POST /api/v1/dashboard/widgets/{widget_id}/data` - Renderiza widget
- ✅ `GET /api/v1/dashboard/widgets/catalog` - Lista widgets disponibles
- ✅ `POST /api/v1/dashboard/template` - Guarda template personalizado (admin only)
- ✅ Validación de permisos por rol
- ✅ Documentación OpenAPI completa

**Archivo:** `app/api/v1/dashboard.py`

```python
"""
Dashboard endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, List

from app.core.database import get_global_db, get_client_db
from app.core.dependencies import get_current_user
from app.models.global_db.user import User
from app.services.widget_service import WidgetService
from app.services.dashboard_service import DashboardService
from app.core.cache import metadata_cache
from app.schemas.dashboard import (
    WidgetDataRequest,
    DashboardLayoutResponse,
    WidgetCatalogResponse,
    SaveTemplateRequest
)


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/layout", response_model=DashboardLayoutResponse)
async def get_dashboard_layout(
    current_user: User = Depends(get_current_user),
    db_global: AsyncSession = Depends(get_global_db)
):
    """
    Obtiene configuración del dashboard según el rol del usuario
    
    Returns:
        Layout con grid de widgets configurado para el rol
    """
    dashboard_service = DashboardService(db_global)
    
    layout = await dashboard_service.get_dashboard_layout(
        tenant_id=current_user.tenant_id,
        role=current_user.role
    )
    
    return {
        'tenant_id': current_user.tenant_id,
        'role': current_user.role,
        'layout': layout
    }


@router.post("/widgets/{widget_id}/data")
async def get_widget_data(
    widget_id: int,
    request: WidgetDataRequest,
    current_user: User = Depends(get_current_user),
    db_global: AsyncSession = Depends(get_global_db),
    db_client: AsyncSession = Depends(get_client_db)
):
    """
    Obtiene datos para un widget específico
    
    Args:
        widget_id: ID del widget en WIDGET_CATALOG
        request: Parámetros del widget (filtros)
    
    Returns:
        Datos formateados según widget_type
    """
    widget_service = WidgetService(metadata_cache, db_client)
    
    try:
        data = await widget_service.render_widget(
            widget_id=widget_id,
            params=request.params,
            tenant_id=current_user.tenant_id
        )
        
        return data
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error rendering widget: {str(e)}"
        )


@router.get("/widgets/catalog", response_model=List[WidgetCatalogResponse])
async def get_widget_catalog(
    current_user: User = Depends(get_current_user),
    db_global: AsyncSession = Depends(get_global_db)
):
    """
    Obtiene catálogo de widgets disponibles
    
    **Requiere rol: admin**
    
    Returns:
        Lista de widgets con sus configuraciones
    """
    # Solo admins pueden ver el catálogo completo
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    widget_service = WidgetService(metadata_cache, db_global)
    widgets = await widget_service.get_all_widgets()
    
    return widgets


@router.post("/template", status_code=status.HTTP_201_CREATED)
async def save_dashboard_template(
    request: SaveTemplateRequest,
    current_user: User = Depends(get_current_user),
    db_global: AsyncSession = Depends(get_global_db)
):
    """
    Guarda template personalizado de dashboard
    
    **Requiere rol: admin**
    
    Args:
        request: Configuración del template (role, layout_config)
    
    Returns:
        Template guardado
    """
    # Solo admins pueden modificar templates
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    dashboard_service = DashboardService(db_global)
    
    template = await dashboard_service.save_custom_template(
        tenant_id=current_user.tenant_id,
        role=request.role,
        layout_config=request.layout_config
    )
    
    return {
        'message': 'Template saved successfully',
        'template_id': template.template_id,
        'role': template.role_access
    }


@router.get("/summary")
async def get_dashboard_summary(
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene resumen general del dashboard
    
    Returns:
        Información general para barra superior
    """
    return {
        'user': {
            'username': current_user.username,
            'role': current_user.role,
            'tenant': current_user.tenant.company_name
        },
        'system': {
            'version': '1.0.0',
            'environment': 'production'
        }
    }
```

**Schemas:**  
**Archivo:** `app/schemas/dashboard.py`

```python
"""
Dashboard schemas
"""
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional


class WidgetDataRequest(BaseModel):
    """Request para obtener datos de widget"""
    params: Dict[str, Any] = Field(..., description="Parámetros del widget (filtros)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "params": {
                    "line_id": 1,
                    "start_date": "2024-01-01T00:00:00",
                    "end_date": "2024-01-31T23:59:59",
                    "interval": "15min"
                }
            }
        }


class DashboardLayoutResponse(BaseModel):
    """Response con layout del dashboard"""
    tenant_id: int
    role: str
    layout: Dict[str, Any]
    
    class Config:
        json_schema_extra = {
            "example": {
                "tenant_id": 1,
                "role": "admin",
                "layout": {
                    "grid": [
                        {"widget_id": 1, "x": 0, "y": 0, "w": 8, "h": 4},
                        {"widget_id": 2, "x": 8, "y": 0, "w": 4, "h": 2}
                    ]
                }
            }
        }


class WidgetCatalogResponse(BaseModel):
    """Response con información de widget del catálogo"""
    widget_id: int
    widget_name: str
    widget_type: str
    description: Optional[str]
    required_params: Dict[str, Any]


class SaveTemplateRequest(BaseModel):
    """Request para guardar template personalizado"""
    role: str = Field(..., pattern="^(admin|viewer|manager)$")
    layout_config: Dict[str, Any]
    
    class Config:
        json_schema_extra = {
            "example": {
                "role": "admin",
                "layout_config": {
                    "grid": [
                        {"widget_id": 1, "x": 0, "y": 0, "w": 12, "h": 4}
                    ]
                }
            }
        }
```


## 📦 TASK 6.4: Tests de Widget Service

**Descripción:**  
Crear tests unitarios e integración para validar el funcionamiento del motor de widgets.

**Criterios de Aceptación:**
- ✅ Test de renderizado de cada tipo de widget
- ✅ Test de validación JSON Schema
- ✅ Test de manejo de errores
- ✅ Test de integración con services
- ✅ Coverage > 80%

**Archivo:** `tests/test_widget_service.py`

```python
"""
Tests para Widget Service
"""
import pytest
from datetime import datetime, timedelta
from app.services.widget_service import WidgetService
from app.core.cache import MetadataCache
from app.models.global_db.template import WidgetCatalog


@pytest.fixture
async def widget_service(test_db_client):
    """Fixture para widget service"""
    cache = MetadataCache()
    await cache.load_metadata(tenant_id=1, db=test_db_client)
    return WidgetService(cache, test_db_client)


@pytest.fixture
async def sample_widget_catalog(test_db_global):
    """Fixture para crear widgets de ejemplo"""
    widgets = [
        WidgetCatalog(
            widget_id=1,
            widget_name="Producción por Tiempo",
            widget_type="line_chart",
            description="Gráfico de línea de producción",
            required_params={
                "type": "object",
                "properties": {
                    "line_id": {"type": "integer"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "interval": {"type": "string"}
                },
                "required": ["line_id", "start_date", "end_date"]
            }
        ),
        WidgetCatalog(
            widget_id=2,
            widget_name="KPI OEE",
            widget_type="kpi_card",
            description="Tarjeta de KPI OEE",
            required_params={
                "type": "object",
                "properties": {
                    "line_id": {"type": "integer"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "kpi_type": {"type": "string"}
                },
                "required": ["line_id", "start_date", "end_date", "kpi_type"]
            }
        )
    ]
    
    for widget in widgets:
        test_db_global.add(widget)
    await test_db_global.commit()
    
    return widgets


@pytest.mark.asyncio
async def test_render_line_chart(widget_service, sample_widget_catalog, seed_detections):
    """Test renderizado de gráfico de línea"""
    params = {
        "line_id": 1,
        "start_date": "2024-01-01T00:00:00",
        "end_date": "2024-01-02T00:00:00",
        "interval": "15min"
    }
    
    result = await widget_service.render_widget(
        widget_id=1,
        params=params,
        tenant_id=1
    )
    
    assert result['widget_id'] == 1
    assert result['widget_type'] == 'line_chart'
    assert 'labels' in result['data']
    assert 'datasets' in result['data']
    assert len(result['data']['datasets']) > 0
    assert result['data']['datasets'][0]['label'] == 'Producción (unidades)'


@pytest.mark.asyncio
async def test_render_kpi_card_oee(widget_service, sample_widget_catalog):
    """Test renderizado de KPI OEE"""
    params = {
        "line_id": 1,
        "start_date": "2024-01-01T00:00:00",
        "end_date": "2024-01-02T00:00:00",
        "kpi_type": "oee"
    }
    
    result = await widget_service.render_widget(
        widget_id=2,
        params=params,
        tenant_id=1
    )
    
    assert result['widget_type'] == 'kpi_card'
    assert 'value' in result['data']
    assert result['data']['unit'] == '%'
    assert result['data']['label'] == 'OEE'
    assert 0 <= result['data']['value'] <= 100


@pytest.mark.asyncio
async def test_invalid_widget_id(widget_service):
    """Test con widget_id inexistente"""
    params = {
        "line_id": 1,
        "start_date": "2024-01-01T00:00:00",
        "end_date": "2024-01-02T00:00:00"
    }
    
    with pytest.raises(ValueError, match="not found in catalog"):
        await widget_service.render_widget(
            widget_id=999,
            params=params,
            tenant_id=1
        )


@pytest.mark.asyncio
async def test_invalid_params_schema(widget_service, sample_widget_catalog):
    """Test con parámetros inválidos según JSON Schema"""
    # Falta parámetro requerido "line_id"
    params = {
        "start_date": "2024-01-01T00:00:00",
        "end_date": "2024-01-02T00:00:00"
    }
    
    with pytest.raises(ValueError, match="Invalid widget parameters"):
        await widget_service.render_widget(
            widget_id=1,
            params=params,
            tenant_id=1
        )


@pytest.mark.asyncio
async def test_render_pie_chart(widget_service, seed_detections):
    """Test renderizado de gráfico de torta"""
    params = {
        "line_id": 1,
        "start_date": "2024-01-01T00:00:00",
        "end_date": "2024-01-02T00:00:00"
    }
    
    # Crear widget de pie_chart en el catálogo
    widget_service.db.add(WidgetCatalog(
        widget_id=3,
        widget_name="Distribución de Productos",
        widget_type="pie_chart",
        required_params={
            "type": "object",
            "properties": {
                "line_id": {"type": "integer"},
                "start_date": {"type": "string"},
                "end_date": {"type": "string"}
            },
            "required": ["line_id", "start_date", "end_date"]
        }
    ))
    await widget_service.db.commit()
    
    result = await widget_service.render_widget(
        widget_id=3,
        params=params,
        tenant_id=1
    )
    
    assert result['widget_type'] == 'pie_chart'
    assert 'labels' in result['data']
    assert 'datasets' in result['data']
    assert len(result['data']['datasets'][0]['data']) > 0


@pytest.mark.asyncio
async def test_render_comparison_bar(widget_service, seed_detections):
    """Test renderizado de comparación entrada/salida"""
    params = {
        "line_id": 1,
        "start_date": "2024-01-01T00:00:00",
        "end_date": "2024-01-02T00:00:00"
    }
    
    widget_service.db.add(WidgetCatalog(
        widget_id=4,
        widget_name="Comparación Entrada/Salida",
        widget_type="comparison_bar",
        required_params={
            "type": "object",
            "properties": {
                "line_id": {"type": "integer"},
                "start_date": {"type": "string"},
                "end_date": {"type": "string"}
            },
            "required": ["line_id", "start_date", "end_date"]
        }
    ))
    await widget_service.db.commit()
    
    result = await widget_service.render_widget(
        widget_id=4,
        params=params,
        tenant_id=1
    )
    
    assert result['widget_type'] == 'comparison_bar'
    assert result['data']['labels'] == ['Entrada', 'Salida', 'Descarte']
    assert len(result['data']['datasets'][0]['data']) == 3


@pytest.mark.asyncio
async def test_render_table_downtimes(widget_service, seed_downtimes):
    """Test renderizado de tabla de paradas"""
    params = {
        "line_id": 1,
        "start_date": "2024-01-01T00:00:00",
        "end_date": "2024-01-02T00:00:00"
    }
    
    widget_service.db.add(WidgetCatalog(
        widget_id=5,
        widget_name="Tabla de Paradas",
        widget_type="table",
        required_params={
            "type": "object",
            "properties": {
                "line_id": {"type": "integer"},
                "start_date": {"type": "string"},
                "end_date": {"type": "string"}
            },
            "required": ["line_id", "start_date", "end_date"]
        }
    ))
    await widget_service.db.commit()
    
    result = await widget_service.render_widget(
        widget_id=5,
        params=params,
        tenant_id=1
    )
    
    assert result['widget_type'] == 'table'
    assert 'columns' in result['data']
    assert 'rows' in result['data']
    assert result['data']['columns'] == ['Inicio', 'Fin', 'Duración', 'Razón']


@pytest.mark.asyncio
async def test_get_all_widgets(widget_service, sample_widget_catalog):
    """Test obtener catálogo completo de widgets"""
    widgets = await widget_service.get_all_widgets()
    
    assert len(widgets) >= 2
    assert all('widget_id' in w for w in widgets)
    assert all('widget_name' in w for w in widgets)
    assert all('widget_type' in w for w in widgets)


@pytest.mark.asyncio
async def test_format_duration(widget_service):
    """Test formateo de duración"""
    # 1 hora, 30 minutos, 45 segundos
    seconds = 3600 + 1800 + 45
    formatted = widget_service._format_duration(seconds)
    assert formatted == "01:30:45"
    
    # 0 horas, 5 minutos, 30 segundos
    seconds = 330
    formatted = widget_service._format_duration(seconds)
    assert formatted == "00:05:30"


@pytest.mark.asyncio
async def test_empty_data_handling(widget_service, sample_widget_catalog):
    """Test manejo de datos vacíos"""
    # Periodo sin datos
    params = {
        "line_id": 1,
        "start_date": "2025-01-01T00:00:00",
        "end_date": "2025-01-02T00:00:00",
        "interval": "15min"
    }
    
    result = await widget_service.render_widget(
        widget_id=1,
        params=params,
        tenant_id=1
    )
    
    # Debe retornar estructura vacía válida
    assert result['data']['labels'] == []
    assert len(result['data']['datasets']) > 0
    assert result['data']['datasets'][0]['data'] == []
```

**Verificación:**

```bash
# Ejecutar tests de widget service
pytest tests/test_widget_service.py -v

# Con coverage
pytest tests/test_widget_service.py --cov=app/services/widget_service --cov-report=html
```

---

## 📦 TASK 6.5: Script de Población de WIDGET_CATALOG

**Descripción:**  
Crear script para poblar `WIDGET_CATALOG` con los widgets del sistema.

**Criterios de Aceptación:**
- ✅ Script ejecutable una sola vez
- ✅ Verifica si ya existe data antes de insertar
- ✅ Inserta todos los widgets necesarios
- ✅ JSON Schema válido para cada widget

**Archivo:** `scripts/seed_widget_catalog.py`

```python
"""
Poblar WIDGET_CATALOG con widgets del sistema
EJECUTAR UNA SOLA VEZ al instalar el sistema
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.database import db_manager
from app.models.global_db.template import WidgetCatalog
from sqlalchemy import text


WIDGETS = [
    {
        "widget_name": "Producción por Tiempo",
        "widget_type": "line_chart",
        "description": "Gráfico de línea mostrando producción a lo largo del tiempo",
        "visibility_rules": {"roles": ["admin", "viewer", "manager"]},
        "required_params": {
            "type": "object",
            "properties": {
                "line_id": {"type": "integer", "description": "ID de la línea de producción"},
                "start_date": {"type": "string", "format": "date-time"},
                "end_date": {"type": "string", "format": "date-time"},
                "interval": {
                    "type": "string",
                    "enum": ["1min", "15min", "1hour", "1day", "1week", "1month"],
                    "default": "15min"
                }
            },
            "required": ["line_id", "start_date", "end_date"]
        }
    },
    {
        "widget_name": "Distribución de Productos",
        "widget_type": "pie_chart",
        "description": "Gráfico de torta mostrando distribución de productos",
        "visibility_rules": {"roles": ["admin", "viewer", "manager"]},
        "required_params": {
            "type": "object",
            "properties": {
                "line_id": {"type": "integer"},
                "start_date": {"type": "string", "format": "date-time"},
                "end_date": {"type": "string", "format": "date-time"}
            },
            "required": ["line_id", "start_date", "end_date"]
        }
    },
    {
        "widget_name": "Detecciones por Área",
        "widget_type": "bar_chart",
        "description": "Gráfico de barras mostrando detecciones por área",
        "visibility_rules": {"roles": ["admin", "manager"]},
        "required_params": {
            "type": "object",
            "properties": {
                "line_id": {"type": "integer"},
                "start_date": {"type": "string", "format": "date-time"},
                "end_date": {"type": "string", "format": "date-time"}
            },
            "required": ["line_id", "start_date", "end_date"]
        }
    },
    {
        "widget_name": "Comparación Entrada/Salida/Descarte",
        "widget_type": "comparison_bar",
        "description": "Comparación de entrada, salida y productos descartados",
        "visibility_rules": {"roles": ["admin", "manager"]},
        "required_params": {
            "type": "object",
            "properties": {
                "line_id": {"type": "integer"},
                "start_date": {"type": "string", "format": "date-time"},
                "end_date": {"type": "string", "format": "date-time"}
            },
            "required": ["line_id", "start_date", "end_date"]
        }
    },
    {
        "widget_name": "KPI - OEE",
        "widget_type": "kpi_card",
        "description": "Tarjeta de KPI mostrando Overall Equipment Effectiveness",
        "visibility_rules": {"roles": ["admin", "viewer", "manager"]},
        "required_params": {
            "type": "object",
            "properties": {
                "line_id": {"type": "integer"},
                "start_date": {"type": "string", "format": "date-time"},
                "end_date": {"type": "string", "format": "date-time"},
                "kpi_type": {"type": "string", "enum": ["oee"], "const": "oee"}
            },
            "required": ["line_id", "start_date", "end_date", "kpi_type"]
        }
    },
    {
        "widget_name": "KPI - Producción Total",
        "widget_type": "kpi_card",
        "description": "Tarjeta de KPI mostrando producción total",
        "visibility_rules": {"roles": ["admin", "viewer", "manager"]},
        "required_params": {
            "type": "object",
            "properties": {
                "line_id": {"type": "integer"},
                "start_date": {"type": "string", "format": "date-time"},
                "end_date": {"type": "string", "format": "date-time"},
                "kpi_type": {"type": "string", "enum": ["total_production"], "const": "total_production"}
            },
            "required": ["line_id", "start_date", "end_date", "kpi_type"]
        }
    },
    {
        "widget_name": "KPI - Peso Total",
        "widget_type": "kpi_card",
        "description": "Tarjeta de KPI mostrando peso total producido",
        "visibility_rules": {"roles": ["admin", "manager"]},
        "required_params": {
            "type": "object",
            "properties": {
                "line_id": {"type": "integer"},
                "start_date": {"type": "string", "format": "date-time"},
                "end_date": {"type": "string", "format": "date-time"},
                "kpi_type": {"type": "string", "enum": ["total_weight"], "const": "total_weight"}
            },
            "required": ["line_id", "start_date", "end_date", "kpi_type"]
        }
    },
    {
        "widget_name": "KPI - Total de Paradas",
        "widget_type": "kpi_card",
        "description": "Tarjeta de KPI mostrando total de paradas",
        "visibility_rules": {"roles": ["admin", "manager"]},
        "required_params": {
            "type": "object",
            "properties": {
                "line_id": {"type": "integer"},
                "start_date": {"type": "string", "format": "date-time"},
                "end_date": {"type": "string", "format": "date-time"},
                "kpi_type": {"type": "string", "enum": ["downtime_count"], "const": "downtime_count"}
            },
            "required": ["line_id", "start_date", "end_date", "kpi_type"]
        }
    },
    {
        "widget_name": "KPI - Disponibilidad",
        "widget_type": "kpi_card",
        "description": "Tarjeta de KPI mostrando disponibilidad",
        "visibility_rules": {"roles": ["admin", "manager"]},
        "required_params": {
            "type": "object",
            "properties": {
                "line_id": {"type": "integer"},
                "start_date": {"type": "string", "format": "date-time"},
                "end_date": {"type": "string", "format": "date-time"},
                "kpi_type": {"type": "string", "enum": ["availability"], "const": "availability"}
            },
            "required": ["line_id", "start_date", "end_date", "kpi_type"]
        }
    },
    {
        "widget_name": "KPI - Rendimiento",
        "widget_type": "kpi_card",
        "description": "Tarjeta de KPI mostrando rendimiento",
        "visibility_rules": {"roles": ["admin", "manager"]},
        "required_params": {
            "type": "object",
            "properties": {
                "line_id": {"type": "integer"},
                "start_date": {"type": "string", "format": "date-time"},
                "end_date": {"type": "string", "format": "date-time"},
                "kpi_type": {"type": "string", "enum": ["performance"], "const": "performance"}
            },
            "required": ["line_id", "start_date", "end_date", "kpi_type"]
        }
    },
    {
        "widget_name": "KPI - Calidad",
        "widget_type": "kpi_card",
        "description": "Tarjeta de KPI mostrando calidad",
        "visibility_rules": {"roles": ["admin", "manager"]},
        "required_params": {
            "type": "object",
            "properties": {
                "line_id": {"type": "integer"},
                "start_date": {"type": "string", "format": "date-time"},
                "end_date": {"type": "string", "format": "date-time"},
                "kpi_type": {"type": "string", "enum": ["quality"], "const": "quality"}
            },
            "required": ["line_id", "start_date", "end_date", "kpi_type"]
        }
    },
    {
        "widget_name": "Tabla de Paradas",
        "widget_type": "table",
        "description": "Tabla mostrando registro de paradas de producción",
        "visibility_rules": {"roles": ["admin", "manager"]},
        "required_params": {
            "type": "object",
            "properties": {
                "line_id": {"type": "integer"},
                "start_date": {"type": "string", "format": "date-time"},
                "end_date": {"type": "string", "format": "date-time"}
            },
            "required": ["line_id", "start_date", "end_date"]
        }
    }
]


async def seed_widgets():
    """Poblar WIDGET_CATALOG con widgets del sistema"""
    print("🚀 Starting WIDGET_CATALOG population...")
    
    db_name = os.getenv('DB_GLOBAL_NAME', 'dashboard_global')
    
    async for session in db_manager.get_session(db_name, is_global=True):
        # Verificar si ya existen widgets
        result = await session.execute(text("SELECT COUNT(*) FROM WIDGET_CATALOG"))
        count = result.scalar()
        
        if count > 0:
            print(f"⚠️  WIDGET_CATALOG already has {count} widgets.")
            print("   Skipping population to avoid duplicates.")
            print("   If you want to repopulate, manually delete existing widgets first.")
            return
        
        # Insertar widgets
        print(f"📦 Inserting {len(WIDGETS)} widgets...")
        
        for widget_data in WIDGETS:
            widget = WidgetCatalog(**widget_data)
            session.add(widget)
        
        await session.commit()
        
        print(f"✅ Successfully inserted {len(WIDGETS)} widgets into WIDGET_CATALOG")
        print("\nWidgets created:")
        for i, widget in enumerate(WIDGETS, 1):
            print(f"  {i}. {widget['widget_name']} ({widget['widget_type']})")


if __name__ == "__main__":
    asyncio.run(seed_widgets())
```

**Verificación:**

```bash
# Ejecutar script de población
python scripts/seed_widget_catalog.py

# Verificar en MySQL
mysql -u root -p dashboard_global
SELECT widget_id, widget_name, widget_type FROM WIDGET_CATALOG;
exit
```

---

## 📦 TASK 6.6: Integración con Frontend - Templates de Widgets

**Descripción:**  
Actualizar templates Flask para renderizar widgets dinámicamente desde el backend.

**Criterios de Aceptación:**
- ✅ Template `widgets_grid.html` implementado
- ✅ Templates individuales por widget_type
- ✅ Integración con Chart.js
- ✅ HTMX para carga dinámica de widgets
- ✅ Loading states y error handling

**Archivo:** `app/templates/dashboard/widgets_grid.html`

```html
<!-- app/templates/dashboard/widgets_grid.html -->
<div 
    id="widgets-grid" 
    class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6"
    hx-get="/api/dashboard/load-widgets"
    hx-trigger="load, refreshWidgets from:body"
    hx-vals='js:{filters: getFilters()}'
    hx-indicator="#widgets-loading"
>
    <!-- Loading State -->
    <div id="widgets-loading" class="htmx-indicator col-span-full">
        <div class="flex items-center justify-center py-12">
            <span class="material-symbols-outlined animate-spin text-4xl text-primary">progress_activity</span>
            <span class="ml-3 text-lg font-medium text-gray-600 dark:text-gray-400">Cargando widgets...</span>
        </div>
    </div>
    
    <!-- Widgets se insertan aquí dinámicamente -->
</div>

<script>
    // Función para obtener filtros actuales
    function getFilters() {
        const form = document.getElementById('filters-form');
        if (!form) return {};
        
        const formData = new FormData(form);
        const filters = {};
        
        for (let [key, value] of formData.entries()) {
            filters[key] = value;
        }
        
        return filters;
    }
    
    // Evento personalizado para refrescar widgets
    function refreshWidgets() {
        document.body.dispatchEvent(new Event('refreshWidgets'));
    }
</script>
```

**Archivo:** `app/templates/dashboard/widgets/line_chart.html`

```html
<!-- app/templates/dashboard/widgets/line_chart.html -->
<div class="bg-white dark:bg-surface-dark rounded-lg shadow-md p-6 fade-in">
    <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-semibold text-gray-900 dark:text-white">
            {{ widget.widget_name }}
        </h3>
        <button 
            onclick="refreshWidget({{ widget.widget_id }})"
            class="text-gray-400 hover:text-primary transition-colors"
        >
            <span class="material-symbols-outlined text-[20px]">refresh</span>
        </button>
    </div>
    
    <div class="relative" style="height: 300px;">
        <canvas id="chart-{{ widget.widget_id }}"></canvas>
    </div>
</div>

<script>
(function() {
    const ctx = document.getElementById('chart-{{ widget.widget_id }}').getContext('2d');
    
    const chartData = {{ widget.data | tojson }};
    
    new Chart(ctx, {
        type: 'line',
        data: chartData,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        color: document.documentElement.classList.contains('dark') ? '#e5e7eb' : '#1f2937'
                    }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: '#fff',
                    bodyColor: '#fff',
                    borderColor: '#2b7cee',
                    borderWidth: 1
                }
            },
            scales: {
                x: {
                    grid: {
                        color: document.documentElement.classList.contains('dark') ? '#374151' : '#e5e7eb'
                    },
                    ticks: {
                        color: document.documentElement.classList.contains('dark') ? '#9ca3af' : '#6b7280'
                    }
                },
                y: {
                    beginAtZero: true,
                    grid: {
                        color: document.documentElement.classList.contains('dark') ? '#374151' : '#e5e7eb'
                    },
                    ticks: {
                        color: document.documentElement.classList.contains('dark') ? '#9ca3af' : '#6b7280',
                        precision: 0
                    }
                }
            }
        }
    });
})();
</script>
```

**Archivo:** `app/templates/dashboard/widgets/kpi_card.html`

```html
<!-- app/templates/dashboard/widgets/kpi_card.html -->
<div class="bg-white dark:bg-surface-dark rounded-lg shadow-md p-6 fade-in">
    <div class="flex items-center justify-between">
        <div class="flex-1">
            <p class="text-sm font-medium text-gray-600 dark:text-gray-400">
                {{ widget.data.label }}
            </p>
            {% if widget.data.subtitle %}
            <p class="text-xs text-gray-500 dark:text-gray-500 mt-1">
                {{ widget.data.subtitle }}
            </p>
            {% endif %}
            <p class="text-3xl font-bold text-gray-900 dark:text-white mt-3">
                {{ widget.data.value }}
                <span class="text-lg font-normal text-gray-600 dark:text-gray-400">
                    {{ widget.data.unit }}
                </span>
            </p>
        </div>
        
        <div class="flex-shrink-0">
            {% if 'oee' in widget.data.label.lower() %}
            <div class="w-16 h-16 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center">
                <span class="material-symbols-outlined text-blue-600 dark:text-blue-400 text-[32px]">analytics</span>
            </div>
            {% elif 'production' in widget.data.label.lower() or 'producción' in widget.data.label.lower() %}
            <div class="w-16 h-16 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center">
                <span class="material-symbols-outlined text-green-600 dark:text-green-400 text-[32px]">inventory_2</span>
            </div>
            {% elif 'parada' in widget.data.label.lower() or 'downtime' in widget.data.label.lower() %}
            <div class="w-16 h-16 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center">
                <span class="material-symbols-outlined text-red-600 dark:text-red-400 text-[32px]">error</span>
            </div>
            {% elif 'disponibilidad' in widget.data.label.lower() or 'availability' in widget.data.label.lower() %}
            <div class="w-16 h-16 bg-purple-100 dark:bg-purple-900/30 rounded-full flex items-center justify-center">
                <span class="material-symbols-outlined text-purple-600 dark:text-purple-400 text-[32px]">schedule</span>
            </div>
            {% else %}
            <div class="w-16 h-16 bg-gray-100 dark:bg-gray-800 rounded-full flex items-center justify-center">
                <span class="material-symbols-outlined text-gray-600 dark:text-gray-400 text-[32px]">monitoring</span>
            </div>
            {% endif %}
        </div>
    </div>
    
    {% if widget.data.trend %}
    <div class="mt-4 flex items-center gap-2">
        {% if widget.data.trend == 'up' %}
        <span class="material-symbols-outlined text-green-600 text-[18px]">trending_up</span>
        <span class="text-sm font-medium text-green-600">+{{ widget.data.change }}%</span>
        {% elif widget.data.trend == 'down' %}
        <span class="material-symbols-outlined text-red-600 text-[18px]">trending_down</span>
        <span class="text-sm font-medium text-red-600">-{{ widget.data.change }}%</span>
        {% else %}
        <span class="material-symbols-outlined text-gray-600 text-[18px]">trending_flat</span>
        <span class="text-sm font-medium text-gray-600">{{ widget.data.change }}%</span>
        {% endif %}
        <span class="text-xs text-gray-500">vs período anterior</span>
    </div>
    {% endif %}
</div>
```

**Archivo:** `app/wsgi.py` (Actualización para widgets)

```python
# Agregar al archivo app/wsgi.py existente

@app.route('/api/dashboard/load-widgets', methods=['POST'])
@login_required
async def load_widgets():
    """
    Endpoint para cargar widgets del dashboard con filtros aplicados
    """
    # Obtener filtros del request
    filters = request.form.to_dict()
    
    # Headers de autenticación
    headers = {'Authorization': f"Bearer {session['access_token']}"}
    
    # Obtener layout del dashboard
    layout_response = await http_client.get(
        '/api/v1/dashboard/layout',
        headers=headers
    )
    
    if layout_response.status_code != 200:
        return '<div class="col-span-full text-center text-red-600">Error al cargar layout</div>', 500
    
    layout = layout_response.json()['layout']
    
    # Renderizar cada widget
    widgets_html = []
    
    for widget_config in layout['grid']:
        widget_id = widget_config['widget_id']
        
        # Combinar filtros con parámetros del widget
        widget_params = {**filters, **widget_config.get('params', {})}
        
        # Obtener datos del widget
        try:
            widget_response = await http_client.post(
                f'/api/v1/dashboard/widgets/{widget_id}/data',
                headers=headers,
                json={'params': widget_params}
            )
            
            if widget_response.status_code == 200:
                widget_data = widget_response.json()
                
                # Renderizar template según widget_type
                widget_html = render_template(
                    f"dashboard/widgets/{widget_data['widget_type']}.html",
                    widget=widget_data,
                    config=widget_config
                )
                widgets_html.append(widget_html)
            else:
                # Widget con error
                widgets_html.append(render_template(
                    'dashboard/widgets/error.html',
                    widget_id=widget_id,
                    error=widget_response.json().get('detail', 'Error desconocido')
                ))
        
        except Exception as e:
            # Widget con excepción
            widgets_html.append(render_template(
                'dashboard/widgets/error.html',
                widget_id=widget_id,
                error=str(e)
            ))
    
    return ''.join(widgets_html)
```

**Archivo:** `app/templates/dashboard/widgets/error.html`

```html
<!-- app/templates/dashboard/widgets/error.html -->
<div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-6 fade-in">
    <div class="flex items-start gap-3">
        <span class="material-symbols-outlined text-red-600 dark:text-red-400 text-[24px]">error</span>
        <div>
            <h4 class="text-sm font-semibold text-red-900 dark:text-red-200">
                Error al cargar widget #{{ widget_id }}
            </h4>
            <p class="text-xs text-red-700 dark:text-red-300 mt-1">
                {{ error }}
            </p>
        </div>
    </div>
</div>
```

---

## ✅ CHECKLIST FINAL - FASE 6

### Widget Service
- [ ] `WidgetService` implementado con routing dinámico
- [ ] 6 tipos de widgets soportados (line_chart, pie_chart, bar_chart, kpi_card, table, comparison_bar)
- [ ] Validación JSON Schema funcional
- [ ] Integración con `detection_service`, `metrics_service`, `downtime_service`
- [ ] Formato de salida compatible con Chart.js
- [ ] Manejo de errores robusto

### Dashboard Service
- [ ] `DashboardService` implementado
- [ ] Templates por defecto para roles (admin, viewer, manager)
- [ ] Soporte para templates personalizados por tenant
- [ ] Método `save_custom_template()` funcional

### API Endpoints
- [ ] `GET /api/v1/dashboard/layout` implementado
- [ ] `POST /api/v1/dashboard/widgets/{widget_id}/data` implementado
- [ ] `GET /api/v1/dashboard/widgets/catalog` implementado
- [ ] `POST /api/v1/dashboard/template` implementado
- [ ] Validación de permisos por rol
- [ ] Documentación OpenAPI completa

### Tests
- [ ] Tests unitarios de `WidgetService` pasando
- [ ] Tests de validación JSON Schema
- [ ] Tests de manejo de datos vacíos
- [ ] Tests de integración con services
- [ ] Coverage > 80%

### Base de Datos
- [ ] Script `seed_widget_catalog.py` ejecutado
- [ ] `WIDGET_CATALOG` poblado con 12 widgets
- [ ] Templates por defecto en código

### Frontend
- [ ] Templates de widgets implementados
- [ ] Integración con Chart.js funcional
- [ ] HTMX para carga dinámica
- [ ] Loading states y error handling
- [ ] Dark mode soportado en gráficos

### Verificación Final
- [ ] Widgets renderizan correctamente en UI
- [ ] Filtros aplicados se reflejan en widgets
- [ ] Diferentes roles ven diferentes layouts
- [ ] Performance aceptable (< 2s para cargar dashboard)
- [ ] No hay errores en logs
- [ ] Documentación actualizada

---

## 🎯 ENTREGABLES DE LA FASE 6

1. **Widget Service completo** con soporte para 6 tipos de widgets
2. **Dashboard Service** con gestión de templates
3. **API Endpoints** para widgets y dashboard
4. **Script de población** de WIDGET_CATALOG ejecutado
5. **Templates Flask** para renderizado de widgets
6. **Tests** con coverage > 80%
7. **Documentación** de uso del motor de widgets
8. **Demo funcional** con al menos 3 widgets en dashboard



# Actualización FASE 6 - Widgets Adicionales

## 📦 TASK 6.7: Implementación de Widgets Adicionales

Agregar 4 nuevos tipos de widgets al sistema:
1. **top_products** - Ranking de productos más producidos
2. **line_status** - Indicador visual del estado actual de la línea
3. **metrics_summary** - Card con resumen de múltiples métricas
4. **events_feed** - Feed de alertas y eventos recientes

---

### Actualización de `widget_service.py`

Agregar los siguientes métodos al archivo `app/services/widget_service.py`:

```python
# Agregar al diccionario widget_renderers en el método render_widget()
widget_renderers = {
    'line_chart': self._render_line_chart,
    'bar_chart': self._render_bar_chart,
    'pie_chart': self._render_pie_chart,
    'kpi_card': self._render_kpi_card,
    'table': self._render_table,
    'comparison_bar': self._render_comparison_bar,
    'top_products': self._render_top_products,         # NUEVO
    'line_status': self._render_line_status,           # NUEVO
    'metrics_summary': self._render_metrics_summary,   # NUEVO
    'events_feed': self._render_events_feed            # NUEVO
}

# Agregar estos métodos a la clase WidgetService:

async def _render_top_products(self, params: Dict) -> Dict:
    """
    Renderiza ranking de productos más producidos
    
    Formato de salida:
    {
        'products': [
            {
                'rank': 1,
                'product_name': 'Producto A',
                'product_code': 'PA001',
                'count': 1500,
                'percentage': 45.5,
                'color': 'rgb(59, 130, 246)',
                'trend': 'up',
                'change': 12.5
            },
            ...
        ],
        'total': 3300
    }
    """
    filters = QueryFilters(**params)
    limit = params.get('limit', 10)  # Top 10 por defecto
    
    # Obtener detecciones
    df = await self.detection_service.get_enriched_detections(filters)
    
    if df.empty:
        return {'products': [], 'total': 0}
    
    # Agrupar por producto y contar
    product_counts = df.groupby(['product_id', 'product_name', 'product_code']).size()
    product_counts = product_counts.reset_index(name='count')
    product_counts = product_counts.sort_values('count', ascending=False)
    
    # Limitar resultados
    top_products = product_counts.head(limit)
    
    # Calcular porcentajes
    total = product_counts['count'].sum()
    top_products['percentage'] = (top_products['count'] / total * 100).round(2)
    
    # Colores para el ranking
    colors = [
        'rgb(59, 130, 246)',   # Blue
        'rgb(16, 185, 129)',   # Green
        'rgb(249, 115, 22)',   # Orange
        'rgb(139, 92, 246)',   # Purple
        'rgb(236, 72, 153)',   # Pink
        'rgb(234, 179, 8)',    # Yellow
        'rgb(239, 68, 68)',    # Red
        'rgb(6, 182, 212)',    # Cyan
        'rgb(245, 158, 11)',   # Amber
        'rgb(168, 85, 247)'    # Violet
    ]
    
    # Formatear resultados
    products_list = []
    for idx, row in top_products.iterrows():
        products_list.append({
            'rank': len(products_list) + 1,
            'product_name': row['product_name'],
            'product_code': row['product_code'],
            'count': int(row['count']),
            'percentage': float(row['percentage']),
            'color': colors[len(products_list) % len(colors)]
        })
    
    return {
        'products': products_list,
        'total': int(total)
    }


async def _render_line_status(self, params: Dict) -> Dict:
    """
    Renderiza indicador visual del estado actual de la línea
    
    Estados posibles:
    - running: Línea operando normalmente
    - stopped: Línea detenida (parada activa)
    - idle: Línea sin actividad reciente
    - warning: Línea con bajo rendimiento
    
    Formato de salida:
    {
        'status': 'running',
        'status_label': 'Operando',
        'line_name': 'Línea Principal',
        'current_speed': 120,  # unidades/hora
        'target_speed': 150,
        'efficiency': 80.0,
        'last_detection': '2024-01-23 14:30:00',
        'uptime_minutes': 120,
        'message': 'Operación normal',
        'alerts': []
    }
    """
    from datetime import datetime, timedelta
    from sqlalchemy import select, desc
    
    line_id = params['line_id']
    
    # Obtener información de la línea
    line = self.cache.get_line(line_id)
    
    if not line:
        raise ValueError(f"Line {line_id} not found")
    
    # Obtener última detección
    table_name = f"detection_line_{line_id}"
    query = f"""
        SELECT detected_at 
        FROM {table_name} 
        ORDER BY detected_at DESC 
        LIMIT 1
    """
    
    result = await self.db.execute(text(query))
    last_detection_row = result.fetchone()
    
    if not last_detection_row:
        return {
            'status': 'idle',
            'status_label': 'Sin Actividad',
            'line_name': line['line_name'],
            'current_speed': 0,
            'target_speed': line['performance'],
            'efficiency': 0.0,
            'last_detection': None,
            'uptime_minutes': 0,
            'message': 'No hay detecciones registradas',
            'alerts': []
        }
    
    last_detection = last_detection_row[0]
    now = datetime.utcnow()
    time_since_last = (now - last_detection).total_seconds()
    
    # Determinar estado
    downtime_threshold = line['downtime_threshold']  # segundos
    
    status = 'idle'
    status_label = 'Inactiva'
    message = 'Sin actividad reciente'
    alerts = []
    
    if time_since_last < downtime_threshold:
        # Línea activa - calcular velocidad actual
        # Contar detecciones de la última hora
        one_hour_ago = now - timedelta(hours=1)
        
        query = f"""
            SELECT COUNT(*) as count
            FROM {table_name}
            WHERE detected_at >= :time_threshold
        """
        
        result = await self.db.execute(
            text(query),
            {'time_threshold': one_hour_ago}
        )
        count_last_hour = result.scalar()
        
        current_speed = count_last_hour  # unidades/hora
        target_speed = line['performance']
        efficiency = (current_speed / target_speed * 100) if target_speed > 0 else 0
        
        # Determinar estado según eficiencia
        if efficiency >= 80:
            status = 'running'
            status_label = 'Operando'
            message = 'Operación normal'
        elif efficiency >= 50:
            status = 'warning'
            status_label = 'Bajo Rendimiento'
            message = f'Eficiencia al {efficiency:.1f}%'
            alerts.append({
                'type': 'warning',
                'message': 'Rendimiento por debajo del objetivo'
            })
        else:
            status = 'warning'
            status_label = 'Crítico'
            message = f'Eficiencia muy baja: {efficiency:.1f}%'
            alerts.append({
                'type': 'error',
                'message': 'Rendimiento crítico - Revisar línea'
            })
        
        # Calcular uptime (desde última parada)
        downtimes = await self.downtime_service.get_recent_downtimes(
            line_id, 
            hours=24
        )
        
        if downtimes:
            last_downtime = max(downtimes, key=lambda x: x['end_time'])
            uptime_minutes = int((now - last_downtime['end_time']).total_seconds() / 60)
        else:
            uptime_minutes = 1440  # 24 horas
        
        return {
            'status': status,
            'status_label': status_label,
            'line_name': line['line_name'],
            'current_speed': current_speed,
            'target_speed': target_speed,
            'efficiency': round(efficiency, 1),
            'last_detection': last_detection.strftime('%Y-%m-%d %H:%M:%S'),
            'uptime_minutes': uptime_minutes,
            'message': message,
            'alerts': alerts
        }
    
    else:
        # Línea detenida
        minutes_stopped = int(time_since_last / 60)
        
        return {
            'status': 'stopped',
            'status_label': 'Detenida',
            'line_name': line['line_name'],
            'current_speed': 0,
            'target_speed': line['performance'],
            'efficiency': 0.0,
            'last_detection': last_detection.strftime('%Y-%m-%d %H:%M:%S'),
            'uptime_minutes': 0,
            'message': f'Parada de {minutes_stopped} minutos',
            'alerts': [{
                'type': 'error',
                'message': f'Línea detenida por {minutes_stopped} minutos'
            }]
        }


async def _render_metrics_summary(self, params: Dict) -> Dict:
    """
    Renderiza card con resumen de múltiples métricas clave
    
    Formato de salida:
    {
        'title': 'Resumen General',
        'period': '01/01/2024 - 31/01/2024',
        'metrics': [
            {
                'label': 'OEE',
                'value': 85.5,
                'unit': '%',
                'icon': 'analytics',
                'color': 'blue',
                'trend': 'up',
                'change': 2.3
            },
            ...
        ]
    }
    """
    filters = QueryFilters(**params)
    
    # Calcular todas las métricas
    oee_metrics = await self.metrics_service.calculate_oee(
        filters.line_id, filters.start_date, filters.end_date
    )
    
    df = await self.detection_service.get_enriched_detections(filters)
    total_production = len(df)
    total_weight = await self.metrics_service.calculate_total_weight(df)
    
    downtimes = await self.downtime_service.get_downtimes(
        filters.line_id, filters.start_date, filters.end_date
    )
    
    # Formatear período
    period = f"{filters.start_date.strftime('%d/%m/%Y')} - {filters.end_date.strftime('%d/%m/%Y')}"
    
    # Construir métricas
    metrics = [
        {
            'label': 'OEE',
            'value': round(oee_metrics['oee'], 1),
            'unit': '%',
            'icon': 'analytics',
            'color': 'blue' if oee_metrics['oee'] >= 80 else 'orange' if oee_metrics['oee'] >= 60 else 'red'
        },
        {
            'label': 'Disponibilidad',
            'value': round(oee_metrics['availability'], 1),
            'unit': '%',
            'icon': 'schedule',
            'color': 'purple'
        },
        {
            'label': 'Rendimiento',
            'value': round(oee_metrics['performance'], 1),
            'unit': '%',
            'icon': 'speed',
            'color': 'green'
        },
        {
            'label': 'Calidad',
            'value': round(oee_metrics['quality'], 1),
            'unit': '%',
            'icon': 'verified',
            'color': 'teal'
        },
        {
            'label': 'Producción',
            'value': total_production,
            'unit': 'unidades',
            'icon': 'inventory_2',
            'color': 'indigo'
        },
        {
            'label': 'Peso Total',
            'value': round(total_weight, 1),
            'unit': 'kg',
            'icon': 'scale',
            'color': 'amber'
        },
        {
            'label': 'Paradas',
            'value': len(downtimes),
            'unit': 'eventos',
            'icon': 'error',
            'color': 'red'
        },
        {
            'label': 'Tiempo de Parada',
            'value': round(sum(d['duration'] for d in downtimes) / 3600, 1),
            'unit': 'horas',
            'icon': 'timer_off',
            'color': 'gray'
        }
    ]
    
    return {
        'title': 'Resumen General',
        'period': period,
        'metrics': metrics
    }


async def _render_events_feed(self, params: Dict) -> Dict:
    """
    Renderiza feed de alertas y eventos importantes
    
    Formato de salida:
    {
        'events': [
            {
                'timestamp': '2024-01-23 14:30:00',
                'type': 'downtime',  # downtime, alert, info, success
                'severity': 'high',  # high, medium, low
                'title': 'Parada de Producción',
                'description': 'Línea detenida por 15 minutos',
                'icon': 'error',
                'color': 'red'
            },
            ...
        ]
    }
    """
    from sqlalchemy import and_, or_
    
    line_id = params['line_id']
    hours_back = params.get('hours_back', 24)  # Últimas 24 horas por defecto
    
    now = datetime.utcnow()
    time_threshold = now - timedelta(hours=hours_back)
    
    events = []
    
    # 1. Obtener paradas recientes
    downtimes = await self.downtime_service.get_downtimes(
        line_id, time_threshold, now
    )
    
    for dt in downtimes:
        duration_minutes = int(dt['duration'] / 60)
        
        # Determinar severidad según duración
        if duration_minutes >= 30:
            severity = 'high'
            color = 'red'
        elif duration_minutes >= 10:
            severity = 'medium'
            color = 'orange'
        else:
            severity = 'low'
            color = 'yellow'
        
        events.append({
            'timestamp': dt['start_time'].strftime('%Y-%m-%d %H:%M:%S'),
            'type': 'downtime',
            'severity': severity,
            'title': 'Parada de Producción',
            'description': f"Línea detenida por {duration_minutes} minutos",
            'icon': 'error',
            'color': color,
            'metadata': {
                'duration': duration_minutes,
                'reason': dt.get('reason', 'No especificada')
            }
        })
    
    # 2. Detectar cambios de producto (usando detecciones)
    query = f"""
        SELECT 
            detected_at,
            product_id,
            LAG(product_id) OVER (ORDER BY detected_at) as prev_product_id
        FROM detection_line_{line_id}
        WHERE detected_at >= :time_threshold
        ORDER BY detected_at DESC
        LIMIT 1000
    """
    
    result = await self.db.execute(
        text(query),
        {'time_threshold': time_threshold}
    )
    
    rows = result.fetchall()
    
    # Identificar cambios de producto
    for row in rows:
        if row[2] and row[1] != row[2]:  # prev_product_id existe y es diferente
            product = self.cache.get_product(row[1])
            prev_product = self.cache.get_product(row[2])
            
            events.append({
                'timestamp': row[0].strftime('%Y-%m-%d %H:%M:%S'),
                'type': 'info',
                'severity': 'low',
                'title': 'Cambio de Producto',
                'description': f"De {prev_product['product_name']} a {product['product_name']}",
                'icon': 'swap_horiz',
                'color': 'blue'
            })
    
    # 3. Detectar picos de producción (producción 20% superior al promedio)
    df = await self.detection_service.get_enriched_detections(
        QueryFilters(
            line_id=line_id,
            start_date=time_threshold,
            end_date=now
        )
    )
    
    if not df.empty:
        # Agrupar por hora
        df['hour'] = df['detected_at'].dt.floor('H')
        hourly_production = df.groupby('hour').size()
        
        if len(hourly_production) > 0:
            avg_production = hourly_production.mean()
            
            for hour, count in hourly_production.items():
                if count > avg_production * 1.2:  # 20% superior
                    events.append({
                        'timestamp': hour.strftime('%Y-%m-%d %H:%M:%S'),
                        'type': 'success',
                        'severity': 'low',
                        'title': 'Pico de Producción',
                        'description': f"{int(count)} unidades producidas (↑{int((count/avg_production - 1) * 100)}%)",
                        'icon': 'trending_up',
                        'color': 'green'
                    })
    
    # 4. Ordenar eventos por timestamp (más recientes primero)
    events.sort(key=lambda x: x['timestamp'], reverse=True)
    
    # Limitar a los últimos 50 eventos
    events = events[:50]
    
    return {
        'events': events,
        'total': len(events),
        'period_hours': hours_back
    }
```

---

### Actualización de `seed_widget_catalog.py`

Agregar estos widgets al array `WIDGETS` en el archivo `scripts/seed_widget_catalog.py`:

```python
# Agregar al final del array WIDGETS:

    {
        "widget_name": "Top de Productos",
        "widget_type": "top_products",
        "description": "Ranking de productos más producidos con porcentajes",
        "visibility_rules": {"roles": ["admin", "manager", "viewer"]},
        "required_params": {
            "type": "object",
            "properties": {
                "line_id": {"type": "integer"},
                "start_date": {"type": "string", "format": "date-time"},
                "end_date": {"type": "string", "format": "date-time"},
                "limit": {"type": "integer", "default": 10, "description": "Número de productos a mostrar"}
            },
            "required": ["line_id", "start_date", "end_date"]
        }
    },
    {
        "widget_name": "Estado de Línea",
        "widget_type": "line_status",
        "description": "Indicador visual del estado actual de la línea de producción",
        "visibility_rules": {"roles": ["admin", "manager", "viewer"]},
        "required_params": {
            "type": "object",
            "properties": {
                "line_id": {"type": "integer"}
            },
            "required": ["line_id"]
        }
    },
    {
        "widget_name": "Resumen de Métricas",
        "widget_type": "metrics_summary",
        "description": "Card compacto con resumen de múltiples métricas clave",
        "visibility_rules": {"roles": ["admin", "manager"]},
        "required_params": {
            "type": "object",
            "properties": {
                "line_id": {"type": "integer"},
                "start_date": {"type": "string", "format": "date-time"},
                "end_date": {"type": "string", "format": "date-time"}
            },
            "required": ["line_id", "start_date", "end_date"]
        }
    },
    {
        "widget_name": "Feed de Eventos",
        "widget_type": "events_feed",
        "description": "Timeline de alertas y eventos importantes recientes",
        "visibility_rules": {"roles": ["admin", "manager"]},
        "required_params": {
            "type": "object",
            "properties": {
                "line_id": {"type": "integer"},
                "hours_back": {"type": "integer", "default": 24, "description": "Horas hacia atrás"}
            },
            "required": ["line_id"]
        }
    }
```

---

### Templates HTML para Nuevos Widgets

**Archivo:** `app/templates/dashboard/widgets/top_products.html`

```html
<!-- app/templates/dashboard/widgets/top_products.html -->
<div class="bg-white dark:bg-surface-dark rounded-lg shadow-md p-6 fade-in">
    <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <span class="material-symbols-outlined text-primary">leaderboard</span>
            Top de Productos
        </h3>
        <span class="text-xs font-medium text-gray-500 dark:text-gray-400">
            Total: {{ widget.data.total }} unidades
        </span>
    </div>
    
    {% if widget.data.products|length > 0 %}
    <div class="space-y-3">
        {% for product in widget.data.products %}
        <div class="group">
            <!-- Header del producto -->
            <div class="flex items-center justify-between mb-1">
                <div class="flex items-center gap-3">
                    <!-- Ranking Badge -->
                    <div class="w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm
                        {% if product.rank == 1 %}bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400
                        {% elif product.rank == 2 %}bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300
                        {% elif product.rank == 3 %}bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-400
                        {% else %}bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400{% endif %}">
                        #{{ product.rank }}
                    </div>
                    
                    <!-- Nombre del producto -->
                    <div>
                        <p class="text-sm font-semibold text-gray-900 dark:text-white">
                            {{ product.product_name }}
                        </p>
                        <p class="text-xs text-gray-500 dark:text-gray-400">
                            {{ product.product_code }}
                        </p>
                    </div>
                </div>
                
                <!-- Cantidad y porcentaje -->
                <div class="text-right">
                    <p class="text-sm font-bold text-gray-900 dark:text-white">
                        {{ product.count }}
                    </p>
                    <p class="text-xs font-medium" style="color: {{ product.color }}">
                        {{ product.percentage }}%
                    </p>
                </div>
            </div>
            
            <!-- Barra de progreso -->
            <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2 overflow-hidden">
                <div 
                    class="h-full rounded-full transition-all duration-500 ease-out"
                    style="background-color: {{ product.color }}; width: {{ product.percentage }}%">
                </div>
            </div>
        </div>
        {% endfor %}
    </div>
    {% else %}
    <div class="text-center py-8">
        <span class="material-symbols-outlined text-gray-400 text-4xl">inventory_2</span>
        <p class="text-sm text-gray-500 dark:text-gray-400 mt-2">
            No hay datos de productos en el período seleccionado
        </p>
    </div>
    {% endif %}
</div>
```

**Archivo:** `app/templates/dashboard/widgets/line_status.html`

```html
<!-- app/templates/dashboard/widgets/line_status.html -->
<div class="bg-white dark:bg-surface-dark rounded-lg shadow-md p-6 fade-in">
    <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-semibold text-gray-900 dark:text-white">
            {{ widget.data.line_name }}
        </h3>
        
        <!-- Status Badge -->
        <div class="px-3 py-1.5 rounded-full text-xs font-bold uppercase tracking-wide flex items-center gap-1.5
            {% if widget.data.status == 'running' %}bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400
            {% elif widget.data.status == 'stopped' %}bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400
            {% elif widget.data.status == 'warning' %}bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400
            {% else %}bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-400{% endif %}">
            <span class="w-2 h-2 rounded-full animate-pulse
                {% if widget.data.status == 'running' %}bg-green-600 dark:bg-green-400
                {% elif widget.data.status == 'stopped' %}bg-red-600 dark:bg-red-400
                {% elif widget.data.status == 'warning' %}bg-yellow-600 dark:bg-yellow-400
                {% else %}bg-gray-600 dark:bg-gray-400{% endif %}">
            </span>
            {{ widget.data.status_label }}
        </div>
    </div>
    
    <!-- Métricas principales -->
    <div class="grid grid-cols-2 gap-4 mb-4">
        <!-- Velocidad actual -->
        <div class="text-center p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
            <p class="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Velocidad Actual</p>
            <p class="text-2xl font-bold text-gray-900 dark:text-white">
                {{ widget.data.current_speed }}
            </p>
            <p class="text-xs text-gray-500 dark:text-gray-400">unidades/hora</p>
        </div>
        
        <!-- Eficiencia -->
        <div class="text-center p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
            <p class="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Eficiencia</p>
            <p class="text-2xl font-bold
                {% if widget.data.efficiency >= 80 %}text-green-600 dark:text-green-400
                {% elif widget.data.efficiency >= 50 %}text-yellow-600 dark:text-yellow-400
                {% else %}text-red-600 dark:text-red-400{% endif %}">
                {{ widget.data.efficiency }}%
            </p>
            <p class="text-xs text-gray-500 dark:text-gray-400">
                de {{ widget.data.target_speed }} u/h
            </p>
        </div>
    </div>
    
    <!-- Barra de progreso de eficiencia -->
    <div class="mb-4">
        <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3 overflow-hidden">
            <div 
                class="h-full rounded-full transition-all duration-500
                {% if widget.data.efficiency >= 80 %}bg-green-500
                {% elif widget.data.efficiency >= 50 %}bg-yellow-500
                {% else %}bg-red-500{% endif %}"
                style="width: {{ widget.data.efficiency }}%">
            </div>
        </div>
    </div>
    
    <!-- Información adicional -->
    <div class="space-y-2 text-sm">
        <div class="flex items-center justify-between py-2 border-b border-gray-200 dark:border-gray-700">
            <span class="text-gray-600 dark:text-gray-400 flex items-center gap-2">
                <span class="material-symbols-outlined text-[18px]">schedule</span>
                Última detección
            </span>
            <span class="font-medium text-gray-900 dark:text-white">
                {% if widget.data.last_detection %}
                    {{ widget.data.last_detection }}
                {% else %}
                    N/A
                {% endif %}
            </span>
        </div>
        
        <div class="flex items-center justify-between py-2 border-b border-gray-200 dark:border-gray-700">
            <span class="text-gray-600 dark:text-gray-400 flex items-center gap-2">
                <span class="material-symbols-outlined text-[18px]">timer</span>
                Tiempo activa
            </span>
            <span class="font-medium text-gray-900 dark:text-white">
                {% if widget.data.uptime_minutes >= 60 %}
                    {{ (widget.data.uptime_minutes / 60) | round(1) }} horas
                {% else %}
                    {{ widget.data.uptime_minutes }} minutos
                {% endif %}
            </span>
        </div>
    </div>
    
    <!-- Mensaje de estado -->
    <div class="mt-4 p-3 rounded-lg
        {% if widget.data.status == 'running' %}bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800
        {% elif widget.data.status == 'stopped' %}bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800
        {% elif widget.data.status == 'warning' %}bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800
        {% else %}bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700{% endif %}">
        <p class="text-sm font-medium
            {% if widget.data.status == 'running' %}text-green-800 dark:text-green-300
            {% elif widget.data.status == 'stopped' %}text-red-800 dark:text-red-300
            {% elif widget.data.status == 'warning' %}text-yellow-800 dark:text-yellow-300
            {% else %}text-gray-800 dark:text-gray-300{% endif %}">
            {{ widget.data.message }}
        </p>
    </div>
    
    <!-- Alertas -->
    {% if widget.data.alerts|length > 0 %}
    <div class="mt-3 space-y-2">
        {% for alert in widget.data.alerts %}
        <div class="flex items-start gap-2 p-2 rounded-lg
            {% if alert.type == 'error' %}bg-red-50 dark:bg-red-900/20
            {% elif alert.type == 'warning' %}bg-yellow-50 dark:bg-yellow-900/20
            {% else %}bg-blue-50 dark:bg-blue-900/20{% endif %}">
            <span class="material-symbols-outlined text-[16px] mt-0.5
                {% if alert.type == 'error' %}text-red-600 dark:text-red-400
                {% elif alert.type == 'warning' %}text-yellow-600 dark:text-yellow-400
                {% else %}text-blue-600 dark:text-blue-400{% endif %}">
                warning
            </span>
            <p class="text-xs font-medium
                {% if alert.type == 'error' %}text-red-700 dark:text-red-300
                {% elif alert.type == 'warning' %}text-yellow-700 dark:text-yellow-300
                {% else %}text-blue-700 dark:text-blue-300{% endif %}">
                {{ alert.message }}
            </p>
        </div>
        {% endfor %}
    </div>
    {% endif %}
</div>
```

**Archivo:** `app/templates/dashboard/widgets/metrics_summary.html`

```html
<!-- app/templates/dashboard/widgets/metrics_summary.html -->
<div class="bg-white dark:bg-surface-dark rounded-lg shadow-md p-6 fade-in">
    <div class="mb-4">
        <h3 class="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <span class="material-symbols-outlined text-primary">dashboard</span>
            {{ widget.data.title }}
        </h3>
        <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
            {{ widget.data.period }}
        </p>
    </div>
    
    <!-- Grid de métricas -->
    <div class="grid grid-cols-2 gap-3">
        {% for metric in widget.data.metrics %}
        <div class="p-3 rounded-lg border border-gray-200 dark:border-gray-700 hover:border-{{ metric.color }}-500 dark:hover:border-{{ metric.color }}-500 transition-colors group">
            <div class="flex items-start justify-between">
                <div class="flex-1">
                    <p class="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                        {{ metric.label }}
                    </p>
                    <p class="text-lg font-bold text-gray-900 dark:text-white">
                        {{ metric.value }}
                        <span class="text-xs font-normal text-gray-500 dark:text-gray-400">
                            {{ metric.unit }}
                        </span>
                    </p>
                </div>
                <div class="w-10 h-10 rounded-lg flex items-center justify-center bg-{{ metric.color }}-100 dark:bg-{{ metric.color }}-900/30 group-hover:scale-110 transition-transform">
                    <span class="material-symbols-outlined text-{{ metric.color }}-600 dark:text-{{ metric.color }}-400 text-[20px]">
                        {{ metric.icon }}
                    </span>
                </div>
            </div>
            
            {% if metric.trend %}
            <div class="mt-2 flex items-center gap-1">
                {% if metric.trend == 'up' %}
                <span class="material-symbols-outlined text-green-600 text-[14px]">trending_up</span>
                <span class="text-xs font-medium text-green-600">+{{ metric.change }}%</span>
                {% elif metric.trend == 'down' %}
                <span class="material-symbols-outlined text-red-600 text-[14px]">trending_down</span>
                <span class="text-xs font-medium text-red-600">-{{ metric.change }}%</span>
                {% endif %}
            </div>
            {% endif %}
        </div>
        {% endfor %}
    </div>
</div>
```

**Archivo:** `app/templates/dashboard/widgets/events_feed.html`

```html
<!-- app/templates/dashboard/widgets/events_feed.html -->
<div class="bg-white dark:bg-surface-dark rounded-lg shadow-md p-6 fade-in">
    <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <span class="material-symbols-outlined text-primary">notifications_active</span>
            Eventos Recientes
        </h3>
        <span class="text-xs font-medium text-gray-500 dark:text-gray-400">
            Últimas {{ widget.data.period_hours }} horas
        </span>
    </div>
    
    {% if widget.data.events|length > 0 %}
    <!-- Timeline de eventos -->
    <div class="relative">
        <!-- Línea vertical -->
        <div class="absolute left-4 top-0 bottom-0 w-0.5 bg-gray-200 dark:bg-gray-700"></div>
        
        <!-- Lista de eventos -->
        <div class="space-y-4 relative">
            {% for event in widget.data.events %}
            <div class="flex gap-4 relative">
                <!-- Icono del evento -->
                <div class="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center z-10 border-2 border-white dark:border-surface-dark
                    {% if event.severity == 'high' %}bg-red-500
                    {% elif event.severity == 'medium' %}bg-yellow-500
                    {% else %}bg-blue-500{% endif %}">
                    <span class="material-symbols-outlined text-white text-[16px]">
                        {{ event.icon }}
                    </span>
                </div>
                
                <!-- Contenido del evento -->
                <div class="flex-1 pb-4">
                    <div class="flex items-start justify-between gap-2 mb-1">
                        <p class="text-sm font-semibold text-gray-900 dark:text-white">
                            {{ event.title }}
                        </p>
                        <span class="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
                            {{ event.timestamp.split(' ')[1] }}
                        </span>
                    </div>
                    
                    <p class="text-xs text-gray-600 dark:text-gray-400 mb-2">
                        {{ event.description }}
                    </p>
                    
                    <!-- Badge de tipo -->
                    <div class="flex items-center gap-2">
                        <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium
                            {% if event.type == 'downtime' %}bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400
                            {% elif event.type == 'alert' %}bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400
                            {% elif event.type == 'success' %}bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400
                            {% else %}bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400{% endif %}">
                            {{ event.type|upper }}
                        </span>
                        
                        <!-- Metadata adicional -->
                        {% if event.metadata %}
                            {% if event.metadata.duration %}
                            <span class="text-xs text-gray-500 dark:text-gray-400">
                                • {{ event.metadata.duration }} min
                            </span>
                            {% endif %}
                        {% endif %}
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
    
    <!-- Ver más -->
    <div class="mt-4 text-center">
        <button class="text-sm font-medium text-primary hover:text-primary-dark transition-colors">
            Ver todos los eventos →
        </button>
    </div>
    {% else %}
    <div class="text-center py-8">
        <span class="material-symbols-outlined text-gray-400 text-4xl">notifications_off</span>
        <p class="text-sm text-gray-500 dark:text-gray-400 mt-2">
            No hay eventos en las últimas {{ widget.data.period_hours }} horas
        </p>
    </div>
    {% endif %}
</div>
```

---

### Actualización del Template Default en `dashboard_service.py`

Agregar los nuevos widgets al layout por defecto:

```python
# En app/services/dashboard_service.py, actualizar _get_default_template()

def _get_default_template(self, role: str) -> Dict:
    """Retorna template por defecto según rol"""
    default_layouts = {
        'admin': {
            'grid': [
                # Fila 1: Estado de línea y métricas resumidas
                {'widget_id': 14, 'x': 0, 'y': 0, 'w': 3, 'h': 3, 'params': {'widget_type': 'line_status'}},
                {'widget_id': 15, 'x': 3, 'y': 0, 'w': 9, 'h': 3, 'params': {'widget_type': 'metrics_summary'}},
                
                # Fila 2: Gráfico de línea grande
                {'widget_id': 1, 'x': 0, 'y': 3, 'w': 8, 'h': 4, 'params': {'widget_type': 'line_chart'}},
                
                # Fila 2: KPIs principales (derecha)
                {'widget_id': 2, 'x': 8, 'y': 3, 'w': 4, 'h': 2, 'params': {'kpi_type': 'oee'}},
                {'widget_id': 3, 'x': 8, 'y': 5, 'w': 4, 'h': 2, 'params': {'kpi_type': 'total_production'}},
                
                # Fila 3: Top productos y Feed eventos
                {'widget_id': 13, 'x': 0, 'y': 7, 'w': 6, 'h': 5, 'params': {'widget_type': 'top_products'}},
                {'widget_id': 16, 'x': 6, 'y': 7, 'w': 6, 'h': 5, 'params': {'widget_type': 'events_feed'}},
                
                # Fila 4: Comparación y distribución
                {'widget_id': 4, 'x': 0, 'y': 12, 'w': 6, 'h': 4, 'params': {'widget_type': 'comparison_bar'}},
                {'widget_id': 5, 'x': 6, 'y': 12, 'w': 6, 'h': 4, 'params': {'widget_type': 'pie_chart'}},
                
                # Fila 5: Tabla de paradas
                {'widget_id': 6, 'x': 0, 'y': 16, 'w': 12, 'h': 4, 'params': {'widget_type': 'table'}},
            ]
        },
        'manager': {
            'grid': [
                # Vista para managers (sin algunos KPIs avanzados)
                {'widget_id': 14, 'x': 0, 'y': 0, 'w': 4, 'h': 3, 'params': {'widget_type': 'line_status'}},
                {'widget_id': 15, 'x': 4, 'y': 0, 'w': 8, 'h': 3, 'params': {'widget_type': 'metrics_summary'}},
                {'widget_id': 1, 'x': 0, 'y': 3, 'w': 8, 'h': 4, 'params': {'widget_type': 'line_chart'}},
                {'widget_id': 2, 'x': 8, 'y': 3, 'w': 4, 'h': 4, 'params': {'kpi_type': 'oee'}},
                {'widget_id': 13, 'x': 0, 'y': 7, 'w': 6, 'h': 5, 'params': {'widget_type': 'top_products'}},
                {'widget_id': 16, 'x': 6, 'y': 7, 'w': 6, 'h': 5, 'params': {'widget_type': 'events_feed'}},
                {'widget_id': 6, 'x': 0, 'y': 12, 'w': 12, 'h': 4, 'params': {'widget_type': 'table'}},
            ]
        },
        'viewer': {
            'grid': [
                # Vista simplificada para viewers
                {'widget_id': 14, 'x': 0, 'y': 0, 'w': 4, 'h': 3, 'params': {'widget_type': 'line_status'}},
                {'widget_id': 1, 'x': 4, 'y': 0, 'w': 8, 'h': 4, 'params': {'widget_type': 'line_chart'}},
                {'widget_id': 2, 'x': 0, 'y': 3, 'w': 4, 'h': 3, 'params': {'kpi_type': 'oee'}},
                {'widget_id': 13, 'x': 0, 'y': 6, 'w': 12, 'h': 5, 'params': {'widget_type': 'top_products'}},
            ]
        }
    }
    
    return default_layouts.get(role, default_layouts['viewer'])
```

---

### Método Auxiliar para Downtime Service

Agregar este método a `app/services/downtime_service.py`:

```python
async def get_recent_downtimes(
    self,
    line_id: int,
    hours: int = 24
) -> List[Dict]:
    """
    Obtiene paradas recientes de las últimas X horas
    
    Args:
        line_id: ID de la línea
        hours: Número de horas hacia atrás
    
    Returns:
        Lista de downtimes
    """
    from datetime import datetime, timedelta
    
    now = datetime.utcnow()
    time_threshold = now - timedelta(hours=hours)
    
    return await self.get_downtimes(line_id, time_threshold, now)
```

---

### Tests Actualizados

Agregar a `tests/test_widget_service.py`:

```python
@pytest.mark.asyncio
async def test_render_top_products(widget_service, seed_detections):
    """Test renderizado de top de productos"""
    params = {
        "line_id": 1,
        "start_date": "2024-01-01T00:00:00",
        "end_date": "2024-01-02T00:00:00",
        "limit": 5
    }
    
    result = await widget_service._render_top_products(params)
    
    assert 'products' in result
    assert 'total' in result
    assert len(result['products']) <= 5
    assert all('rank' in p for p in result['products'])
    assert all('percentage' in p for p in result['products'])


@pytest.mark.asyncio
async def test_render_line_status_running(widget_service, seed_recent_detections):
    """Test renderizado de estado de línea - operando"""
    params = {"line_id": 1}
    
    result = await widget_service._render_line_status(params)
    
    assert 'status' in result
    assert result['status'] in ['running', 'stopped', 'idle', 'warning']
    assert 'efficiency' in result
    assert 'current_speed' in result
    assert 'last_detection' in result


@pytest.mark.asyncio
async def test_render_metrics_summary(widget_service, seed_detections):
    """Test renderizado de resumen de métricas"""
    params = {
        "line_id": 1,
        "start_date": "2024-01-01T00:00:00",
        "end_date": "2024-01-02T00:00:00"
    }
    
    result = await widget_service._render_metrics_summary(params)
    
    assert 'title' in result
    assert 'period' in result
    assert 'metrics' in result
    assert len(result['metrics']) == 8  # 8 métricas definidas
    assert all('label' in m for m in result['metrics'])
    assert all('value' in m for m in result['metrics'])
    assert all('icon' in m for m in result['metrics'])


@pytest.mark.asyncio
async def test_render_events_feed(widget_service, seed_downtimes):
    """Test renderizado de feed de eventos"""
    params = {
        "line_id": 1,
        "hours_back": 24
    }
    
    result = await widget_service._render_events_feed(params)
    
    assert 'events' in result
    assert 'total' in result
    assert 'period_hours' in result
    assert all('timestamp' in e for e in result['events'])
    assert all('type' in e for e in result['events'])
    assert all('severity' in e for e in result['events'])
```

---

## ✅ CHECKLIST ACTUALIZADO - FASE 6

### Widgets Originales
- [ ] line_chart ✓
- [ ] pie_chart ✓
- [ ] bar_chart ✓
- [ ] kpi_card ✓
- [ ] table ✓
- [ ] comparison_bar ✓

### Widgets Nuevos
- [ ] top_products (Ranking de productos)
- [ ] line_status (Estado de línea)
- [ ] metrics_summary (Resumen de métricas)
- [ ] events_feed (Feed de eventos)

### Total de Widgets
- [ ] 10 tipos de widgets implementados
- [ ] `WIDGET_CATALOG` con 16 widgets (12 originales + 4 nuevos)
- [ ] Templates HTML para todos los tipos
- [ ] Tests para nuevos widgets
- [ ] Documentación actualizada

---

## 🎯 ENTREGABLES ACTUALIZADOS

1. **Widget Service** con 10 tipos de widgets (6 originales + 4 nuevos)
2. **16 widgets** en WIDGET_CATALOG
3. **Templates HTML** para todos los widgets
4. **Dashboard layouts** actualizados con nuevos widgets
5. **Tests completos** con coverage > 80%
6. **Demo funcional** mostrando todos los widgets

---

Los nuevos widgets agregan funcionalidades críticas para el monitoreo en tiempo real y análisis de producción. El **line_status** permite ver el estado actual de manera visual, el **top_products** identifica los productos más producidos, el **metrics_summary** ofrece una vista consolidada de todas las métricas clave, y el **events_feed** mantiene al usuario informado sobre eventos importantes en tiempo real.



---

## 📝 NOTAS IMPORTANTES

### Extensibilidad del Sistema

Para agregar un nuevo tipo de widget:

1. **Agregar al catálogo:**
```python
# En scripts/seed_widget_catalog.py
{
    "widget_name": "Nuevo Widget",
    "widget_type": "nuevo_tipo",
    "required_params": {...}
}
```

2. **Implementar renderer:**
```python
# En app/services/widget_service.py
async def _render_nuevo_tipo(self, params: Dict) -> Dict:
    # Lógica del widget
    return {...}
```

3. **Crear template:**
```html
<!-- app/templates/dashboard/widgets/nuevo_tipo.html -->
```

4. **Actualizar routing:**
```python
widget_renderers = {
    ...
    'nuevo_tipo': self._render_nuevo_tipo
}
```

### Performance Tips

- Los widgets comparten el mismo `detection_service`, por lo que las consultas se benefician del caché
- Para dashboards con muchos widgets, considerar lazy loading
- Cache de resultados de widgets por 1-5 minutos (futuro)

### Próximos Pasos

- **FASE 7:** Implementar frontend completo con panel de filtros
- **FASE 8:** Implementar seguridad OWASP
- **FASE 9:** Optimización y performance
- **FASE 10:** Deployment en cPanel