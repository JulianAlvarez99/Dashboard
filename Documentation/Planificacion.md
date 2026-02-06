Planificación del Proyecto (Roadmap) - Camet Analytics (Flask Edition)
Estado Actual
Hemos completado la Fase 0: Arquitectura y Diseño. Contamos con:
Esquema de Base de Datos v2.4 (Auth, Planta, Big Data, UI, Sistema).
Estrategia de "Motor de Reglas" y "Application-Side Joins".
Prompt de diseño para generación de UI estática.
FASE 1: Fundaciones y Autenticación (Semana 1-2)
Objetivos:
✅ Setup inicial del proyecto
✅ Configuración de bases de datos
✅ Sistema de autenticación completo
✅ RBAC básico
Tareas Detalladas:
1.1 Setup del Proyecto
bash
# Estructura básica
- Crear estructura de carpetas
- Configurar requirements.txt
- Setup .env files
- Configurar logging

1.2 Configuración de Bases de Datos
python
# app/core/database.py
- Crear engine para DB_GLOBAL
- Crear engine dinámico para DB_CLIENT_{tenant_id}
- Implementar SessionLocal factory
- Context manager para transacciones

1.3 Modelos de Autenticación
python
# app/models/global_db/
- TENANT model
- USER model (con permissions JSON)
- USER_LOGIN model
- AUDIT_LOG model

1.4 Sistema de Autenticación
python
# app/core/security.py
- Hash de passwords (Argon2)
- Generación de JWT (access + refresh tokens)
- Validación de tokens
- CSRF token generation


# app/api/v1/auth.py
- POST /api/v1/auth/login
- POST /api/v1/auth/logout
- POST /api/v1/auth/refresh
- GET /api/v1/auth/me

1.5 Middleware de Seguridad
python
# app/middleware/
- Rate limiting (100 req/min por IP)
- Security headers (OWASP)
- Tenant context injection
- Audit logging automático

Deliverables:
Login funcional con JWT
Registro en AUDIT_LOG de todas las acciones
Manejo de sesiones con timeout (configurable)
Tests unitarios de autenticación

FASE 2: Sistema de Caché y Metadatos (Semana 2-3)
Objetivos:
✅ Cargar metadatos en memoria al inicio
✅ Sistema de actualización de caché
✅ CRUD de configuración de planta
Tareas Detalladas:
2.1 Modelos de Cliente
python
# app/models/client_db/
- PRODUCTION_LINE
- AREA
- PRODUCT
- FILTER
- SHIFT
- FAILURE / INCIDENT

2.2 Sistema de Caché
python
# app/core/cache.py
class MetadataCache:
    """
    Cache en memoria con TTL configurable
    """
    def __init__(self):
        self._cache = {
            'products': {},      # {product_id: product_dict}
            'areas': {},         # {area_id: area_dict}
            'lines': {},         # {line_id: line_dict}
            'filters': {},
            'shifts': {}
        }
        self._last_updated = None
    
    async def load_metadata(self, tenant_id: int):
        """Carga inicial desde DB"""
        
    async def get_product(self, product_id: int):
        """Obtiene producto del cache"""
        
    async def refresh(self, tenant_id: int):
        """Recarga metadatos si hay cambios"""

2.3 Endpoints de Configuración
python
# app/api/v1/production.py
- GET    /api/v1/production/lines
- POST   /api/v1/production/lines
- PUT    /api/v1/production/lines/{id}
- DELETE /api/v1/production/lines/{id}

- GET    /api/v1/production/areas
- POST   /api/v1/production/areas
# ... similar para products, filters, shifts

2.4 Service de Inicialización
python
# app/services/cache_service.py
async def initialize_tenant_cache(tenant_id: int):
    """
    Carga metadatos al iniciar la app o al login del usuario
    """
    cache = MetadataCache()
    await cache.load_metadata(tenant_id)
    return cache

Deliverables:
Metadatos cargados en memoria (< 1s al inicio)
CRUD completo de configuración de planta
Sistema de invalidación de caché al modificar datos
Tests de performance del caché

FASE 3: Motor de Consultas Dinámicas (Semana 3-4)
Objetivos:
✅ Query builder genérico
✅ Particionamiento de tablas DETECTION
✅ Application-side joins eficientes
Tareas Detalladas:
3.1 Gestión de Particiones
python
# app/utils/partition_manager.py
class PartitionManager:
    async def create_monthly_partition(
        self, 
        table_name: str, 
        year: int, 
        month: int
    ):
        """
        CREATE TABLE detection_line_1 (
            ...
        ) PARTITION BY RANGE (YEAR(detected_at)*100 + MONTH(detected_at)) (
            PARTITION p202401 VALUES LESS THAN (202402),
            PARTITION p202402 VALUES LESS THAN (202403),
            ...
        );
        """

3.2 Query Builder
python
# app/services/query_builder.py
class DetectionQueryBuilder:
    def __init__(self, cache: MetadataCache):
        self.cache = cache
    
    def build_detection_query(
        self,
        line_id: int,
        start_date: datetime,
        end_date: datetime,
        product_ids: Optional[List[int]] = None,
        area_ids: Optional[List[int]] = None,
        shift_id: Optional[int] = None
    ) -> str:
        """
        Genera query optimizado con filtros
        Retorna SQL parametrizado
        """
        # Determinar particiones necesarias
        partitions = self._get_required_partitions(start_date, end_date)
        
        # Construir WHERE clause
        filters = []
        filters.append(f"detected_at BETWEEN :start AND :end")
        
        if product_ids:
            filters.append(f"product_id IN :products")
        
        if area_ids:
            filters.append(f"area_id IN :areas")
        
        # Si hay filtro de turno, agregar lógica de tiempo
        if shift_id:
            shift = await self.cache.get_shift(shift_id)
            # Lógica de turnos overnight, etc.
        
        query = f"""
            SELECT * FROM detection_line_{line_id}
            WHERE {' AND '.join(filters)}
        """
        
        return query

3.3 Detection Service
python
# app/services/detection_service.py
class DetectionService:
    async def get_enriched_detections(
        self,
        filters: QueryFilters
    ) -> pd.DataFrame:
        """
        1. Ejecuta query crudo
        2. Carga a DataFrame
        3. Enriquece con metadatos del cache
        4. Retorna datos listos para visualización
        """
        # Ejecutar query
        raw_data = await self.repo.execute_raw_query(query, params)
        
        # Convertir a DataFrame
        df = pd.DataFrame(raw_data)
        
        # Enriquecer con cache (app-side join)
        df['product_name'] = df['product_id'].map(
            lambda x: self.cache.get_product(x)['product_name']
        )
        df['area_name'] = df['area_id'].map(
            lambda x: self.cache.get_area(x)['area_name']
        )
        
        return df

3.4 Paginación Eficiente
python
# app/schemas/query.py
class PaginatedQuery(BaseModel):
    page: int = 1
    page_size: int = 1000
    filters: QueryFilters

# En el service
async def get_paginated_detections(
    self,
    paginated_query: PaginatedQuery
) -> Dict:
    offset = (paginated_query.page - 1) * paginated_query.page_size
    
    # Agregar LIMIT y OFFSET al query
    query += f" LIMIT {paginated_query.page_size} OFFSET {offset}"
    
    # Obtener total count (usar COUNT(*) sin LIMIT)
    total = await self.repo.count(filters)
    
    return {
        'data': df.to_dict('records'),
        'total': total,
        'page': paginated_query.page,
        'pages': math.ceil(total / paginated_query.page_size)
    }

Deliverables:
Query builder genérico funcional
Particionamiento automático de DETECTION_LINE_X
Paginación eficiente (queries < 200ms con 100k registros)
Tests de rendimiento con datasets grandes

FASE 4: Cálculo de Paradas (Downtime) (Semana 4-5)
Objetivos:
✅ Algoritmo de cálculo de paradas
✅ Registro en DOWNTIME_EVENTS_X
✅ Background task para procesamiento
Tareas Detalladas:
4.1 Downtime Service
python
# app/services/downtime_service.py
class DowntimeService:
    async def calculate_downtimes(
        self,
        line_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict]:
        """
        Algoritmo:
        1. Obtener área de salida de la línea
        2. Ordenar detecciones por detected_at ASC
        3. Calcular diff entre detecciones consecutivas
        4. Si diff > downtime_threshold -> registrar parada
        """
        # Obtener threshold de la línea
        line = await self.cache.get_line(line_id)
        threshold_seconds = line['downtime_threshold']
        
        # Obtener área de salida (asumiendo area_order más alto)
        output_area = await self.get_output_area(line_id)
        
        # Query de detecciones del área de salida
        detections = await self.detection_service.get_detections(
            line_id=line_id,
            area_ids=[output_area['area_id']],
            start_date=start_date,
            end_date=end_date
        )
        
        downtimes = []
        prev_time = None
        
        for detection in detections:
            current_time = detection['detected_at']
            
            if prev_time:
                diff_seconds = (current_time - prev_time).total_seconds()
                
                if diff_seconds > threshold_seconds:
                    downtimes.append({
                        'start_time': prev_time,
                        'end_time': current_time,
                        'duration': diff_seconds,
                        'reason_code': None,  # Se puede asignar manualmente
                        'reason': 'Auto-detected downtime'
                    })
            
            prev_time = current_time
        
        # Guardar en DOWNTIME_EVENTS_{line_id}
        await self.save_downtimes(line_id, downtimes)
        
        return downtimes

4.2 Background Task (usando APScheduler)
python
# app/tasks/downtime_calculator.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job('interval', minutes=15)
async def auto_calculate_downtimes():
    """
    Ejecuta cada 15 minutos para todas las líneas activas
    """
    active_lines = await get_active_lines()
    
    for line in active_lines:
        # Calcular paradas de las últimas 15 minutos
        start = datetime.now() - timedelta(minutes=15)
        end = datetime.now()
        
        await downtime_service.calculate_downtimes(
            line_id=line['line_id'],
            start_date=start,
            end_date=end
        )

Pregunta sobre Background Tasks:
¿Por qué background tasks?
Para calcular paradas en tiempo real sin bloquear la UI
Para mantener DOWNTIME_EVENTS_ actualizado
Para mantenimiento de particiones (crear/eliminar automáticamente)
Para limpiar sesiones expiradas
Alternativa sin Celery: Usaremos APScheduler que corre en el mismo proceso de FastAPI, no requiere broker (Redis/RabbitMQ) y es más ligero para cPanel.
Deliverables:
Algoritmo de cálculo de paradas funcional
Background task ejecutándose cada 15 min
Endpoint para recalcular paradas manualmente
Tests del algoritmo con casos edge (turnos overnight, etc.)

FASE 5: Cálculo de Métricas (KPIs) (Semana 5-6)
Objetivos:
✅ OEE (Overall Equipment Effectiveness)
✅ Eficiencia, Calidad, Rendimiento
✅ Agregaciones por intervalo (1min, 15min, 1h, etc.)
Tareas Detalladas:
5.1 Metrics Service
python
# app/services/metrics_service.py
class MetricsService:
    async def calculate_oee(
        self,
        line_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """
        OEE = Availability × Performance × Quality
        
        Availability = (Operating Time / Planned Production Time)
        Performance = (Actual Production / Target Production)
        Quality = (Good Units / Total Units)
        """
        line = await self.cache.get_line(line_id)
        
        # Tiempo planificado (según turnos configurados)
        planned_time = await self.calculate_planned_time(
            line_id, start_date, end_date
        )
        
        # Tiempo de paradas
        downtimes = await self.downtime_service.get_downtimes(
            line_id, start_date, end_date
        )
        total_downtime = sum(d['duration'] for d in downtimes)
        
        # Operating Time = Planned Time - Downtime
        operating_time = planned_time - total_downtime
        
        # Availability
        availability = (operating_time / planned_time) * 100 if planned_time > 0 else 0
        
        # Performance
        detections = await self.detection_service.get_detections(
            line_id=line_id,
            start_date=start_date,
            end_date=end_date
        )
        actual_production = len(detections)
        
        # Target production = production_std × operating_time (en horas)
        target_production = (
            line['performance'] * (operating_time / 3600)
        )
        
        performance = (actual_production / target_production) * 100 if target_production > 0 else 0
        
        # Quality (comparar entrada vs salida)
        input_area = await self.get_input_area(line_id)
        output_area = await self.get_output_area(line_id)
        
        input_count = await self.count_detections(line_id, input_area['area_id'], start_date, end_date)
        output_count = await self.count_detections(line_id, output_area['area_id'], start_date, end_date)
        
        quality = (output_count / input_count) * 100 if input_count > 0 else 100
        
        # OEE
        oee = (availability * performance * quality) / 10000
        
        return {
            'oee': round(oee, 2),
            'availability': round(availability, 2),
            'performance': round(performance, 2),
            'quality': round(quality, 2),
            'total_production': actual_production,
            'good_units': output_count,
            'rejected_units': input_count - output_count,
            'downtime_count': len(downtimes),
            'total_downtime_seconds': total_downtime,
            'planned_time_seconds': planned_time,
            'operating_time_seconds': operating_time
        }
    
    async def calculate_planned_time(
        self,
        line_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> float:
        """
        Calcula tiempo planificado según turnos configurados
        Retorna segundos
        """
        shifts = await self.cache.get_shifts_for_line(line_id)
        
        total_seconds = 0
        current_date = start_date.date()
        end_date_only = end_date.date()
        
        while current_date <= end_date_only:
            day_name = current_date.strftime('%A')
            
            for shift in shifts:
                # Verificar si el turno aplica este día
                if day_name in shift['days_implemented']:
                    shift_start = datetime.combine(current_date, shift['start_time'])
                    shift_end = datetime.combine(current_date, shift['end_time'])
                    
                    # Manejar turnos overnight
                    if shift['is_overnight']:
                        shift_end += timedelta(days=1)
                    
                    # Calcular intersección con el rango solicitado
                    effective_start = max(shift_start, start_date)
                    effective_end = min(shift_end, end_date)
                    
                    if effective_end > effective_start:
                        total_seconds += (effective_end - effective_start).total_seconds()
            
            current_date += timedelta(days=1)
        
        return total_seconds

5.2 Agregaciones por Intervalo
python
async def aggregate_by_interval(
    self,
    df: pd.DataFrame,
    interval: str  # '1min', '15min', '1H', '1D', '1W', '1M'
) -> pd.DataFrame:
    """
    Agrupa detecciones por intervalo de tiempo
    """
    if df.empty:
        return pd.DataFrame()
    
    df['detected_at'] = pd.to_datetime(df['detected_at'])
    
    # Mapeo de intervalos personalizados
    interval_map = {
        '1min': '1T',
        '15min': '15T',
        '1hour': '1H',
        '1day': '1D',
        '1week': '1W',
        '1month': '1M'
    }
    
    resample_interval = interval_map.get(interval, interval)
    
    # Resample según intervalo
    aggregated = df.set_index('detected_at').resample(resample_interval).agg({
        'detection_id': 'count',
        'product_id': lambda x: x.mode()[0] if len(x) > 0 else None,
        'area_id': lambda x: x.mode()[0] if len(x) > 0 else None,
    }).rename(columns={'detection_id': 'count'})
    
    # Enriquecer con nombres (si existen en el df original)
    if 'product_name' in df.columns:
        product_names = df.groupby('product_id')['product_name'].first()
        aggregated['product_name'] = aggregated['product_id'].map(product_names)
    
    return aggregated.reset_index()

5.3 Cálculo de Peso Total
async def aggregate_by_interval(
    self,
    df: pd.DataFrame,
    interval: str  # '1min', '15min', '1H', '1D', '1W', '1M'
) -> pd.DataFrame:
    """
    Agrupa detecciones por intervalo de tiempo
    """
    if df.empty:
        return pd.DataFrame()
    
    df['detected_at'] = pd.to_datetime(df['detected_at'])
    
    # Mapeo de intervalos personalizados
    interval_map = {
        '1min': '1T',
        '15min': '15T',
        '1hour': '1H',
        '1day': '1D',
        '1week': '1W',
        '1month': '1M'
    }
    
    resample_interval = interval_map.get(interval, interval)
    
    # Resample según intervalo
    aggregated = df.set_index('detected_at').resample(resample_interval).agg({
        'detection_id': 'count',
        'product_id': lambda x: x.mode()[0] if len(x) > 0 else None,
        'area_id': lambda x: x.mode()[0] if len(x) > 0 else None,
    }).rename(columns={'detection_id': 'count'})
    
    # Enriquecer con nombres (si existen en el df original)
    if 'product_name' in df.columns:
        product_names = df.groupby('product_id')['product_name'].first()
        aggregated['product_name'] = aggregated['product_id'].map(product_names)
    
    return aggregated.reset_index()


# app/api/v1/dashboard.py
@router.post("/metrics/oee")
async def get_oee_metrics(
    filters: QueryFilters,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Calcula métricas OEE para una línea y rango de fechas
    """
    metrics = await metrics_service.calculate_oee(
        line_id=filters.line_id,
        start_date=filters.start_date,
        end_date=filters.end_date
    )
    
    # Registrar consulta en USER_QUERY
    await audit_service.log_query(
        user_id=current_user.user_id,
        query_type='oee_metrics',
        filters=filters.dict()
    )
    
    return metrics

@router.post("/metrics/summary")
async def get_production_summary(
    filters: QueryFilters,
    current_user: User = Depends(get_current_user)
):
    """
    Retorna resumen de producción con múltiples métricas
    """
    # Obtener detecciones
    df = await detection_service.get_enriched_detections(filters)
    
    # Calcular métricas
    total_production = len(df)
    total_weight = await metrics_service.calculate_total_weight(df)
    
    # Distribución por producto
    product_distribution = df.groupby('product_name').size().to_dict()
    
    # Paradas
    downtimes = await downtime_service.get_downtimes(
        filters.line_id,
        filters.start_date,
        filters.end_date
    )
    
    return {
        'total_production': total_production,
        'total_weight': round(total_weight, 2),
        'product_distribution': product_distribution,
        'downtime_count': len(downtimes),
        'total_downtime_seconds': sum(d['duration'] for d in downtimes)
    }

Deliverables:
Cálculo de OEE funcional y validado
Agregaciones por intervalo optimizadas
Endpoints para obtener métricas
Tests unitarios de cálculos con casos edge

FASE 6: Motor de Widgets (Semana 6-7)
Objetivos:
✅ Interpretación de WIDGET_CATALOG
✅ Renderizado de DASHBOARD_TEMPLATE
✅ Widgets dinámicos con Chart.js
Tareas Detalladas:
6.1 Widget Service
python
# app/services/widget_service.py
from jsonschema import validate, ValidationError

class WidgetService:
    def __init__(self, cache: MetadataCache, db: AsyncSession):
        self.cache = cache
        self.db = db
        self.detection_service = DetectionService(cache, db)
        self.metrics_service = MetricsService(cache, db)
    
    async def render_widget(
        self,
        widget_id: int,
        params: Dict,
        tenant_id: int
    ) -> Dict:
        """
        1. Obtiene configuración del widget de WIDGET_CATALOG
        2. Valida params con required_params (JSON Schema)
        3. Obtiene datos según widget_type
        4. Retorna datos formateados para Chart.js
        """
        # Obtener widget config de DB_GLOBAL
        widget = await self.get_widget_config(widget_id)
        
        # Validar params contra JSON Schema
        try:
            validate(instance=params, schema=widget['required_params'])
        except ValidationError as e:
            raise ValueError(f"Invalid widget parameters: {e.message}")
        
        # Routing según widget_type
        widget_renderers = {
            'line_chart': self.render_line_chart,
            'bar_chart': self.render_bar_chart,
            'pie_chart': self.render_pie_chart,
            'kpi_card': self.render_kpi_card,
            'table': self.render_table,
            'comparison_bar': self.render_comparison_bar
        }
        
        renderer = widget_renderers.get(widget['widget_type'])
        if not renderer:
            raise ValueError(f"Unknown widget type: {widget['widget_type']}")
        
        data = await renderer(params)
        
        return {
            'widget_id': widget_id,
            'widget_name': widget['widget_name'],
            'widget_type': widget['widget_type'],
            'data': data
        }
    
    async def render_line_chart(self, params: Dict) -> Dict:
        """
        Gráfico de línea de producción por tiempo
        """
        # Obtener detecciones
        filters = QueryFilters(**params)
        df = await self.detection_service.get_enriched_detections(filters)
        
        # Agrupar por intervalo
        aggregated = await self.metrics_service.aggregate_by_interval(
            df, params.get('interval', '15min')
        )
        
        # Formato Chart.js
        return {
            'labels': aggregated['detected_at'].dt.strftime('%Y-%m-%d %H:%M').tolist(),
            'datasets': [{
                'label': 'Producción',
                'data': aggregated['count'].tolist(),
                'borderColor': 'rgb(59, 130, 246)',
                'backgroundColor': 'rgba(59, 130, 246, 0.1)',
                'tension': 0.4,
                'fill': True
            }]
        }
    
    async def render_pie_chart(self, params: Dict) -> Dict:
        """
        Distribución de productos
        """
        filters = QueryFilters(**params)
        df = await self.detection_service.get_enriched_detections(filters)
        
        # Agrupar por producto
        product_dist = df.groupby('product_name').size()
        
        # Colores dinámicos
        colors = [
            'rgb(59, 130, 246)',
            'rgb(16, 185, 129)',
            'rgb(249, 115, 22)',
            'rgb(139, 92, 246)',
            'rgb(236, 72, 153)',
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
    
    async def render_comparison_bar(self, params: Dict) -> Dict:
        """
        Comparación Entrada vs Salida vs Descarte
        """
        filters = QueryFilters(**params)
        line_id = params['line_id']
        
        # Obtener áreas
        input_area = await self.get_input_area(line_id)
        output_area = await self.get_output_area(line_id)
        
        # Contar detecciones por área
        input_count = await self.detection_service.count_detections(
            line_id, input_area['area_id'], 
            filters.start_date, filters.end_date
        )
        
        output_count = await self.detection_service.count_detections(
            line_id, output_area['area_id'],
            filters.start_date, filters.end_date
        )
        
        rejected = input_count - output_count
        
        return {
            'labels': ['Entrada', 'Salida', 'Descarte'],
            'datasets': [{
                'label': 'Unidades',
                'data': [input_count, output_count, rejected],
                'backgroundColor': [
                    'rgba(16, 185, 129, 0.8)',
                    'rgba(59, 130, 246, 0.8)',
                    'rgba(239, 68, 68, 0.8)'
                ],
                'borderColor': [
                    'rgb(16, 185, 129)',
                    'rgb(59, 130, 246)',
                    'rgb(239, 68, 68)'
                ],
                'borderWidth': 2
            }]
        }
    
    async def render_kpi_card(self, params: Dict) -> Dict:
        """
        KPI individual (número grande)
        """
        kpi_type = params.get('kpi_type')
        filters = QueryFilters(**params)
        
        if kpi_type == 'oee':
            metrics = await self.metrics_service.calculate_oee(
                filters.line_id, filters.start_date, filters.end_date
            )
            value = metrics['oee']
            unit = '%'
        
        elif kpi_type == 'total_production':
            df = await self.detection_service.get_enriched_detections(filters)
            value = len(df)
            unit = 'unidades'
        
        elif kpi_type == 'total_weight':
            df = await self.detection_service.get_enriched_detections(filters)
            value = await self.metrics_service.calculate_total_weight(df)
            unit = 'kg'
        
        elif kpi_type == 'downtime_count':
            downtimes = await self.downtime_service.get_downtimes(
                filters.line_id, filters.start_date, filters.end_date
            )
            value = len(downtimes)
            unit = 'paradas'
        
        else:
            raise ValueError(f"Unknown KPI type: {kpi_type}")
        
        return {
            'value': round(value, 2) if isinstance(value, float) else value,
            'unit': unit,
            'label': kpi_type.replace('_', ' ').title()
        }
    
    async def render_table(self, params: Dict) -> Dict:
        """
        Tabla de paradas
        """
        filters = QueryFilters(**params)
        downtimes = await self.downtime_service.get_downtimes(
            filters.line_id, filters.start_date, filters.end_date
        )
        
        # Formatear para tabla
        rows = []
        for dt in downtimes:
            rows.append({
                'start_time': dt['start_time'].strftime('%Y-%m-%d %H:%M:%S'),
                'end_time': dt['end_time'].strftime('%Y-%m-%d %H:%M:%S'),
                'duration': self._format_duration(dt['duration']),
                'reason': dt.get('reason', 'N/A')
            })
        
        return {
            'columns': ['Inicio', 'Fin', 'Duración', 'Razón'],
            'rows': rows
        }
    
    def _format_duration(self, seconds: float) -> str:
        """Formatea duración en formato legible"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

6.2 Dashboard Template Service
python
# app/services/dashboard_service.py
class DashboardService:
    async def get_dashboard_layout(
        self,
        tenant_id: int,
        role: str
    ) -> Dict:
        """
        Obtiene layout del dashboard según rol del usuario
        """
        # Buscar template específico para el rol
        template = await self.db.execute(
            select(DashboardTemplate).where(
                and_(
                    DashboardTemplate.tenant_id == tenant_id,
                    DashboardTemplate.role_access == role
                )
            )
        )
        template = template.scalar_one_or_none()
        
        if not template:
            # Usar template por defecto
            template = await self.get_default_template(role)
        
        return template.layout_config
    
    async def get_default_template(self, role: str) -> DashboardTemplate:
        """
        Retorna template por defecto según rol
        """
        default_layouts = {
            'admin': {
                'grid': [
                    {'widget_id': 1, 'x': 0, 'y': 0, 'w': 8, 'h': 4},  # Line chart
                    {'widget_id': 2, 'x': 8, 'y': 0, 'w': 4, 'h': 2},  # KPI OEE
                    {'widget_id': 3, 'x': 8, 'y': 2, 'w': 4, 'h': 2},  # KPI Production
                    {'widget_id': 4, 'x': 0, 'y': 4, 'w': 6, 'h': 4},  # Comparison bar
                    {'widget_id': 5, 'x': 6, 'y': 4, 'w': 6, 'h': 4},  # Pie chart
                    {'widget_id': 6, 'x': 0, 'y': 8, 'w': 12, 'h': 4}, # Downtime table
                ]
            },
            'viewer': {
                'grid': [
                    {'widget_id': 1, 'x': 0, 'y': 0, 'w': 12, 'h': 4}, # Line chart
                    {'widget_id': 2, 'x': 0, 'y': 4, 'w': 6, 'h': 2},  # KPI OEE
                    {'widget_id': 5, 'x': 6, 'y': 4, 'w': 6, 'h': 4},  # Pie chart
                ]
            }
        }
        
        return DashboardTemplate(
            tenant_id=0,  # Template del sistema
            role_access=role,
            layout_config=default_layouts.get(role, default_layouts['viewer'])
        )

6.3 Endpoints de Dashboard
python
# app/api/v1/dashboard.py
@router.get("/dashboard/layout")
async def get_dashboard_layout(
    current_user: User = Depends(get_current_user)
):
    """
    Retorna configuración del dashboard para el rol del usuario
    """
    layout = await dashboard_service.get_dashboard_layout(
        tenant_id=current_user.tenant_id,
        role=current_user.role
    )
    return layout

@router.post("/dashboard/widgets/{widget_id}/data")
async def get_widget_data(
    widget_id: int,
    params: Dict,
    current_user: User = Depends(get_current_user)
):
    """
    Retorna datos para un widget específico
    """
    # Validar que el usuario tiene permiso para ver este widget
    # (según su DASHBOARD_TEMPLATE)
    
    data = await widget_service.render_widget(
        widget_id=widget_id,
        params=params,
        tenant_id=current_user.tenant_id
    )
    
    return data

@router.get("/dashboard/widgets/catalog")
async def get_widget_catalog(
    current_user: User = Depends(get_current_user)
):
    """
    Retorna catálogo de widgets disponibles
    (solo para admins que configuran dashboards)
    """
    if current_user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    widgets = await widget_service.get_all_widgets()
    return widgets

Deliverables:
Motor de widgets funcional con validación JSON Schema
Al menos 6 tipos de widgets implementados:
Line Chart (producción por tiempo)
Pie Chart (distribución de productos)
Bar Chart (comparación entrada/salida/descarte)
KPI Cards (OEE, producción total, peso, paradas)
Table (tabla de paradas)
Sistema de templates dinámico por rol
Tests de renderizado de widgets

FASE 7: Frontend con Flask + Jinja2 + HTMX (Semana 7-8)
Objetivos:
✅ Templates responsivos con Tailwind CSS
✅ HTMX para interactividad sin JS pesado
✅ Chart.js para gráficos
✅ Panel de filtros dinámico
Tareas Detalladas:
7.1 Configuración de Flask
python
# app/wsgi.py
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from flask_wtf.csrf import CSRFProtect
import httpx
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['API_BASE_URL'] = os.getenv('API_BASE_URL', 'http://localhost:8000')

csrf = CSRFProtect(app)

# Cliente HTTP para comunicarse con FastAPI
http_client = httpx.AsyncClient(base_url=app.config['API_BASE_URL'])

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'access_token' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
async def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Llamar a API de autenticación
        response = await http_client.post('/api/v1/auth/login', json={
            'username': username,
            'password': password
        })
        
        if response.status_code == 200:
            data = response.json()
            session['access_token'] = data['access_token']
            session['user'] = data['user']
            return redirect(url_for('dashboard'))
        else:
            return render_template('auth/login.html', error='Credenciales inválidas')
    
    return render_template('auth/login.html')

@app.route('/logout')
async def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
async def dashboard():
    # Obtener layout del dashboard
    headers = {'Authorization': f"Bearer {session['access_token']}"}
    
    layout_response = await http_client.get('/api/v1/dashboard/layout', headers=headers)
    layout = layout_response.json()
    
    # Obtener metadatos para filtros
    lines_response = await http_client.get('/api/v1/production/lines', headers=headers)
    products_response = await http_client.get('/api/v1/production/products', headers=headers)
    shifts_response = await http_client.get('/api/v1/production/shifts', headers=headers)
    
    return render_template('dashboard/index.html',
        user=session['user'],
        layout=layout,
        production_lines=lines_response.json(),
        products=products_response.json(),
        shifts=shifts_response.json()
    )

@app.route('/api/dashboard/apply-filters', methods=['POST'])
@login_required
async def apply_filters():
    """
    Endpoint para HTMX que retorna HTML de widgets actualizados
    """
    filters = request.form.to_dict()
    headers = {'Authorization': f"Bearer {session['access_token']}"}
    
    # Obtener layout
    layout_response = await http_client.get('/api/v1/dashboard/layout', headers=headers)
    layout = layout_response.json()
    
    # Renderizar widgets con los filtros aplicados
    widgets_html = []
    for widget_config in layout['grid']:
        widget_id = widget_config['widget_id']
        
        # Obtener datos del widget
        widget_response = await http_client.post(
            f'/api/v1/dashboard/widgets/{widget_id}/data',
            headers=headers,
            json=filters
        )
        widget_data = widget_response.json()
        
        # Renderizar widget
        widget_html = render_template(
            f"dashboard/widgets/{widget_data['widget_type']}.html",
            widget=widget_data,
            config=widget_config
        )
        widgets_html.append(widget_html)
    
    return ''.join(widgets_html)

if __name__ == '__main__':
    app.run(debug=True, port=5000)

7.2 Layout Base Completo
html
<!-- app/templates/base.html -->
<!DOCTYPE html>
<html class="dark" lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Dashboard - Camet Analytics{% endblock %}</title>
    
    <!-- Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
    
    <!-- Google Fonts: Inter -->
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet"/>
    
    <!-- Material Symbols -->
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet"/>
    
    <!-- Tailwind Configuration -->
    <script id="tailwind-config">
        tailwind.config = {
            darkMode: "class",
            theme: {
                extend: {
                    colors: {
                        "primary": "#2b7cee",
                        "primary-dark": "#1a5bb5",
                        "background-light": "#F3F4F6",
                        "background-dark": "#0f172a",
                        "surface-light": "#FFFFFF",
                        "surface-dark": "#1e293b",
                        "text-main": "#1e293b",
                        "text-sub": "#64748b",
                        "border-light": "#e2e8f0",
                    },
                    fontFamily: {
                        "display": ["Inter", "sans-serif"],
                        "body": ["Inter", "sans-serif"],
                    },
                    borderRadius: {
                        "DEFAULT": "0.375rem",
                        "lg": "0.5rem",
                        "xl": "0.75rem",
                        "full": "9999px"
                    },
                },
            },
        }
    </script>
    
    <!-- Custom Styles -->
    <style>
        body {
            font-family: 'Inter', sans-serif;
        }
        
        /* Custom Scrollbar */
        .custom-scrollbar::-webkit-scrollbar {
            width: 4px;
            height: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
            background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
            background-color: #cbd5e1;
            border-radius: 20px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
            background-color: #94a3b8;
        }
        
        /* Material Icons Filled Variant */
        .icon-filled {
            font-variation-settings: 'FILL' 1, 'wght' 400, 'GRAD' 0, 'opsz' 24;
        }
        
        /* HTMX Loading Indicators */
        .htmx-indicator {
            display: none;
        }
        .htmx-request .htmx-indicator {
            display: inline-block;
        }
        .htmx-request.htmx-indicator {
            display: inline-block;
        }
        
        /* Loading Spinner Animation */
        @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }
        .animate-spin {
            animation: spin 1s linear infinite;
        }
        
        /* Pulse Animation for Active States */
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .animate-pulse {
            animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        }
        
        /* Chart Line Animation */
        .sparkline-path {
            stroke-dasharray: 100;
            stroke-dashoffset: 0;
            animation: dash 2s ease-in-out;
        }
        @keyframes dash {
            from { stroke-dashoffset: 100; }
            to { stroke-dashoffset: 0; }
        }
        
        /* Fade In Animation */
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .fade-in {
            animation: fadeIn 0.3s ease-out;
        }
    </style>
    
    <!-- CSRF Token -->
    <meta name="csrf-token" content="{{ csrf_token() }}">
    
    <!-- Extra Head Block -->
    {% block extra_head %}{% endblock %}
</head>
<body class="bg-background-light dark:bg-background-dark text-text-main dark:text-gray-100 flex h-screen overflow-hidden">
    
    {% block body %}
    <!-- Default body content (can be overridden) -->
    <div class="flex-1 flex items-center justify-center">
        <p class="text-text-sub">No content available</p>
    </div>
    {% endblock %}
    
    <!-- Toast Notifications Container -->
    <div id="toast-container" class="fixed top-4 right-4 z-50 space-y-2">
        <!-- Toasts will be inserted here dynamically -->
    </div>
    
    <!-- Global Scripts -->
    <script>
        // Configure HTMX with CSRF Token
        document.body.addEventListener('htmx:configRequest', (event) => {
            const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
            event.detail.headers['X-CSRFToken'] = csrfToken;
        });
        
        // Toast Notification System
        function showToast(message, type = 'info') {
            const container = document.getElementById('toast-container');
            const toast = document.createElement('div');
            
            const colors = {
                'success': 'bg-green-500',
                'error': 'bg-red-500',
                'warning': 'bg-yellow-500',
                'info': 'bg-blue-500'
            };
            
            const icons = {
                'success': 'check_circle',
                'error': 'error',
                'warning': 'warning',
                'info': 'info'
            };
            
            toast.className = `${colors[type]} text-white px-6 py-4 rounded-lg shadow-lg flex items-center gap-3 min-w-[300px] fade-in`;
            toast.innerHTML = `
                <span class="material-symbols-outlined">${icons[type]}</span>
                <span class="flex-1">${message}</span>
                <button onclick="this.parentElement.remove()" class="hover:bg-white/20 rounded p-1">
                    <span class="material-symbols-outlined text-[18px]">close</span>
                </button>
            `;
            
            container.appendChild(toast);
            
            // Auto-remove after 5 seconds
            setTimeout(() => {
                toast.style.opacity = '0';
                toast.style.transform = 'translateX(100%)';
                toast.style.transition = 'all 0.3s ease-out';
                setTimeout(() => toast.remove(), 300);
            }, 5000);
        }
        
        // Global error handler for HTMX
        document.body.addEventListener('htmx:responseError', (event) => {
            showToast('Error al cargar los datos. Intente nuevamente.', 'error');
        });
        
        // Global success handler for HTMX
        document.body.addEventListener('htmx:afterSwap', (event) => {
            // Reinitialize any charts or interactive elements after HTMX swap
            if (typeof initializeCharts === 'function') {
                initializeCharts();
            }
        });
    </script>
    
    {% block scripts %}{% endblock %}
</body>
</html>


FASE 7: Frontend con Flask + Jinja2 + HTMX (Semana 7-8) - Continuación
7.3 Panel de Filtros Completo con HTMX
html
<!-- app/templates/dashboard/filters.html -->
<div class="bg-white dark:bg-surface-dark rounded-lg shadow-md p-6 sticky top-0 z-20" 
     x-data="filterPanel()"
     x-init="init()">
     
    <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <span class="material-symbols-outlined text-primary">tune</span>
            Filtros de Consulta
        </h3>
        <button 
            @click="resetFilters()"
            class="text-xs text-text-sub hover:text-primary transition-colors flex items-center gap-1">
            <span class="material-symbols-outlined text-[16px]">restart_alt</span>
            Restablecer
        </button>
    </div>
    
    <form 
        hx-post="/api/dashboard/apply-filters" 
        hx-target="#widgets-container"
        hx-swap="innerHTML"
        hx-indicator="#loading-indicator"
        class="space-y-4">
        
        <!-- Row 1: Basic Filters -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            
            <!-- Line Selection -->
            <div>
                <label class="block text-xs font-bold text-text-sub uppercase tracking-wide mb-2">
                    Línea de Producción
                </label>
                <div class="relative">
                    <select 
                        name="line_id" 
                        required
                        x-model="filters.line_id"
                        class="w-full appearance-none px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-md bg-gray-50 dark:bg-gray-800 text-text-main dark:text-white focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent text-sm">
                        <option value="">Seleccione una línea</option>
                        {% for line in production_lines %}
                        <option value="{{ line.line_id }}">{{ line.line_name }}</option>
                        {% endfor %}
                    </select>
                    <span class="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-text-sub pointer-events-none text-[20px]">
                        expand_more
                    </span>
                </div>
            </div>
            
            <!-- Product Selection -->
            <div>
                <label class="block text-xs font-bold text-text-sub uppercase tracking-wide mb-2">
                    Producto
                </label>
                <div class="relative">
                    <select 
                        name="product_ids" 
                        x-model="filters.product_ids"
                        multiple
                        size="1"
                        class="w-full appearance-none px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-md bg-gray-50 dark:bg-gray-800 text-text-main dark:text-white focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent text-sm">
                        <option value="">Todos los productos</option>
                        {% for product in products %}
                        <option value="{{ product.product_id }}">{{ product.product_name }}</option>
                        {% endfor %}
                    </select>
                    <span class="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-text-sub pointer-events-none text-[20px]">
                        expand_more
                    </span>
                </div>
                <p class="text-xs text-text-sub mt-1">Mantener Ctrl para seleccionar múltiples</p>
            </div>
            
            <!-- Interval Selection -->
            <div>
                <label class="block text-xs font-bold text-text-sub uppercase tracking-wide mb-2">
                    Intervalo de Agregación
                </label>
                <div class="relative">
                    <select 
                        name="interval"
                        x-model="filters.interval"
                        class="w-full appearance-none px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-md bg-gray-50 dark:bg-gray-800 text-text-main dark:text-white focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent text-sm">
                        <option value="1min">1 Minuto</option>
                        <option value="15min" selected>15 Minutos</option>
                        <option value="1hour">1 Hora</option>
                        <option value="1day">1 Día</option>
                        <option value="1week">1 Semana</option>
                        <option value="1month">1 Mes</option>
                    </select>
                    <span class="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-text-sub pointer-events-none text-[20px]">
                        expand_more
                    </span>
                </div>
            </div>
        </div>
        
        <!-- Divider -->
        <div class="border-t border-gray-200 dark:border-gray-700"></div>
        
        <!-- Row 2: Date & Time Filters -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            
            <!-- Start Date -->
            <div>
                <label class="block text-xs font-bold text-text-sub uppercase tracking-wide mb-2">
                    Fecha de Inicio
                </label>
                <div class="relative">
                    <input 
                        type="date" 
                        name="start_date" 
                        required
                        x-model="filters.start_date"
                        class="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-md bg-gray-50 dark:bg-gray-800 text-text-main dark:text-white focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent text-sm"
                    />
                    <span class="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-text-sub pointer-events-none text-[20px]">
                        calendar_today
                    </span>
                </div>
            </div>
            
            <!-- Start Time -->
            <div>
                <label class="block text-xs font-bold text-text-sub uppercase tracking-wide mb-2">
                    Hora de Inicio
                </label>
                <div class="relative">
                    <input 
                        type="time" 
                        name="start_time" 
                        required
                        x-model="filters.start_time"
                        class="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-md bg-gray-50 dark:bg-gray-800 text-text-main dark:text-white focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent text-sm"
                    />
                    <span class="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-text-sub pointer-events-none text-[20px]">
                        schedule
                    </span>
                </div>
            </div>
            
            <!-- End Date -->
            <div>
                <label class="block text-xs font-bold text-text-sub uppercase tracking-wide mb-2">
                    Fecha de Fin
                </label>
                <div class="relative">
                    <input 
                        type="date" 
                        name="end_date" 
                        required
                        x-model="filters.end_date"
                        class="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-md bg-gray-50 dark:bg-gray-800 text-text-main dark:text-white focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent text-sm"
                    />
                    <span class="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-text-sub pointer-events-none text-[20px]">
                        calendar_today
                    </span>
                </div>
            </div>
            
            <!-- End Time -->
            <div>
                <label class="block text-xs font-bold text-text-sub uppercase tracking-wide mb-2">
                    Hora de Fin
                </label>
                <div class="relative">
                    <input 
                        type="time" 
                        name="end_time" 
                        required
                        x-model="filters.end_time"
                        class="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-md bg-gray-50 dark:bg-gray-800 text-text-main dark:text-white focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent text-sm"
                    />
                    <span class="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-text-sub pointer-events-none text-[20px]">
                        schedule
                    </span>
                </div>
            </div>
        </div>
        
        <!-- Row 3: Additional Filters -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            
            <!-- Shift Selection -->
            <div>
                <label class="block text-xs font-bold text-text-sub uppercase tracking-wide mb-2">
                    Turno
                </label>
                <div class="relative">
                    <select 
                        name="shift_id"
                        x-model="filters.shift_id"
                        class="w-full appearance-none px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-md bg-gray-50 dark:bg-gray-800 text-text-main dark:text-white focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent text-sm">
                        <option value="">Todos los turnos</option>
                        {% for shift in shifts %}
                        <option value="{{ shift.shift_id }}">{{ shift.shift_name }}</option>
                        {% endfor %}
                    </select>
                    <span class="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-text-sub pointer-events-none text-[20px]">
                        expand_more
                    </span>
                </div>
            </div>
            
            <!-- Downtime Threshold -->
            <div>
                <label class="block text-xs font-bold text-text-sub uppercase tracking-wide mb-2">
                    Umbral de Parada (min)
                </label>
                <div class="relative">
                    <input 
                        type="number" 
                        name="downtime_threshold"
                        x-model="filters.downtime_threshold"
                        min="1"
                        max="60"
                        value="5"
                        class="w-full px-3 py-2 pr-12 border border-gray-300 dark:border-gray-700 rounded-md bg-gray-50 dark:bg-gray-800 text-text-main dark:text-white focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent text-sm"
                    />
                    <span class="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-text-sub font-bold">
                        MIN
                    </span>
                </div>
            </div>
            
            <!-- Display Options -->
            <div class="flex items-end">
                <label class="flex items-center gap-2 cursor-pointer group">
                    <input 
                        type="checkbox" 
                        name="display_stops"
                        x-model="filters.display_stops"
                        class="w-4 h-4 rounded border-gray-300 text-primary focus:ring-primary"
                    />
                    <span class="text-sm font-medium text-text-main dark:text-white group-hover:text-primary transition-colors">
                        Mostrar Paradas
                    </span>
                </label>
            </div>
        </div>
        
        <!-- Action Buttons -->
        <div class="flex items-center justify-between pt-4 border-t border-gray-200 dark:border-gray-700">
            
            <!-- Quick Presets -->
            <div class="flex gap-2">
                <button 
                    type="button"
                    @click="applyPreset('today')"
                    class="px-3 py-1.5 text-xs font-medium text-text-sub hover:text-primary hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md transition-colors">
                    Hoy
                </button>
                <button 
                    type="button"
                    @click="applyPreset('yesterday')"
                    class="px-3 py-1.5 text-xs font-medium text-text-sub hover:text-primary hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md transition-colors">
                    Ayer
                </button>
                <button 
                    type="button"
                    @click="applyPreset('last7days')"
                    class="px-3 py-1.5 text-xs font-medium text-text-sub hover:text-primary hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md transition-colors">
                    Últimos 7 días
                </button>
            </div>
            
            <!-- Submit & Export Buttons -->
            <div class="flex gap-3">
                <button 
                    type="button"
                    class="px-4 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 text-text-main dark:text-white text-sm font-medium rounded-md hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center gap-2 transition-colors">
                    <span class="material-symbols-outlined text-[18px]">file_download</span>
                    Exportar
                </button>
                
                <button 
                    type="submit"
                    class="px-6 py-2 bg-primary text-white text-sm font-bold uppercase rounded-md hover:bg-primary-dark flex items-center gap-2 shadow-sm shadow-blue-200 dark:shadow-none transition-all">
                    <span class="htmx-indicator">
                        <span class="material-symbols-outlined animate-spin text-[18px]">progress_activity</span>
                    </span>
                    <span class="material-symbols-outlined text-[18px]">search</span>
                    Aplicar Filtros
                </button>
            </div>
        </div>
        
        <!-- Loading Indicator -->
        <div id="loading-indicator" class="htmx-indicator mt-4 flex items-center justify-center gap-2 text-primary">
            <span class="material-symbols-outlined animate-spin">progress_activity</span>
            <span class="text-sm font-medium">Cargando datos...</span>
        </div>
    </form>
</div>

<!-- Alpine.js Logic for Filter Panel -->
<script>
function filterPanel() {
    return {
        filters: {
            line_id: '',
            product_ids: [],
            interval: '15min',
            start_date: '',
            start_time: '00:00',
            end_date: '',
            end_time: '23:59',
            shift_id: '',
            downtime_threshold: 5,
            display_stops: true
        },
        
        init() {
            // Set default date range (last 24 hours)
            this.applyPreset('today');
        },
        
        formatDate(date) {
            const year = date.getFullYear();
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            return `${year}-${month}-${day}`;
        },
        
        applyPreset(preset) {
            const now = new Date();
            const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
            
            switch(preset) {
                case 'today':
                    this.filters.start_date = this.formatDate(today);
                    this.filters.end_date = this.formatDate(today);
                    this.filters.start_time = '00:00';
                    this.filters.end_time = '23:59';
                    break;
                    
                case 'yesterday':
                    const yesterday = new Date(today);
                    yesterday.setDate(yesterday.getDate() - 1);
                    this.filters.start_date = this.formatDate(yesterday);
                    this.filters.end_date = this.formatDate(yesterday);
                    this.filters.start_time = '00:00';
                    this.filters.end_time = '23:59';
                    break;
                    
                case 'last7days':
                    const weekAgo = new Date(today);
                    weekAgo.setDate(weekAgo.getDate() - 7);
                    this.filters.start_date = this.formatDate(weekAgo);
                    this.filters.end_date = this.formatDate(today);
                    this.filters.start_time = '00:00';
                    this.filters.end_time = '23:59';
                    break;
            }
        },
        
        resetFilters() {
            this.filters = {
                line_id: '',
                product_ids: [],
                interval: '15min',
                start_date: '',
                start_time: '00:00',
                end_date: '',
                end_time: '23:59',
                shift_id: '',
                downtime_threshold: 5,
                display_stops: true
            };
            this.applyPreset('today');
        }
    }
}
</script>


📦 Dependencias Necesarias para Alpine.js
Agregar al base.html antes del cierre de </head>:
html
<!-- Alpine.js para lógica reactiva -->
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.13.3/dist/cdn.min.js"></script>

<!-- HTMX para interactividad -->
<script src="https://unpkg.com/htmx.org@1.9.10"></script>

7.4 Dashboard Principal
html
<!-- app/templates/dashboard/index.html -->
{% extends "base.html" %}

{% block title %}Dashboard - {{ user.username }}{% endblock %}

{% block content %}
<div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
    <!-- Panel de Filtros (columna izquierda en desktop) -->
    <div class="lg:col-span-1">
        {% include "dashboard/filters.html" %}
    </div>
    
    <!-- Widgets Grid (columna derecha en desktop) -->
    <div class="lg:col-span-3">
        <div id="widgets-container" class="space-y-6">
            <!-- Mensaje inicial -->
            <div class="bg-blue-50 border border-blue-200 rounded-lg p-8 text-center">
                <svg class="mx-auto h-12 w-12 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
                </svg>
                <h3 class="mt-4 text-lg font-medium text-gray-900">
                    Seleccione los filtros para visualizar datos
                </h3>
                <p class="mt-2 text-sm text-gray-600">
                    Configure los parámetros de consulta en el panel de la izquierda y haga clic en "Aplicar Filtros"
                </p>
            </div>
        </div>
    </div>
</div>
{% endblock %}

7.5 Widgets Individuales
html
<!-- app/templates/dashboard/widgets/line_chart.html -->
<div class="bg-white rounded-lg shadow-md p-6">
    <h3 class="text-lg font-semibold text-gray-900 mb-4">
        {{ widget.data.title | default('Producción por Tiempo') }}
    </h3>
    <div class="relative" style="height: 300px;">
        <canvas id="chart-{{ widget.widget_id }}"></canvas>
    </div>
</div>

<script>
(function() {
    const ctx = document.getElementById('chart-{{ widget.widget_id }}').getContext('2d');
    new Chart(ctx, {
        type: 'line',
        data: {{ widget.data | tojson }},
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        precision: 0
                    }
                }
            }
        }
    });
})();
</script>

html
<!-- app/templates/dashboard/widgets/pie_chart.html -->
<div class="bg-white rounded-lg shadow-md p-6">
    <h3 class="text-lg font-semibold text-gray-900 mb-4">
        Distribución de Productos
    </h3>
    <div class="relative" style="height: 300px;">
        <canvas id="pie-chart-{{ widget.widget_id }}"></canvas>
    </div>
</div>

<script>
(function() {
    const ctx = document.getElementById('pie-chart-{{ widget.widget_id }}').getContext('2d');
    new Chart(ctx, {
        type: 'pie',
        data: {{ widget.data | tojson }},
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                }
            }
        }
    });
})();
</script>

html
<!-- app/templates/dashboard/widgets/bar_chart.html -->
<div class="bg-white rounded-lg shadow-md p-6">
    <h3 class="text-lg font-semibold text-gray-900 mb-4">
        Comparación Entrada vs Salida
    </h3>
    <div class="relative" style="height: 300px;">
        <canvas id="bar-chart-{{ widget.widget_id }}"></canvas>
    </div>
</div>

<script>
(function() {
    const ctx = document.getElementById('bar-chart-{{ widget.widget_id }}').getContext('2d');
    new Chart(ctx, {
        type: 'bar',
        data: {{ widget.data | tojson }},
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
})();
</script>

html
<!-- app/templates/dashboard/widgets/kpi_card.html -->
<div class="bg-white rounded-lg shadow-md p-6">
    <div class="flex items-center justify-between">
        <div>
            <p class="text-sm font-medium text-gray-600">{{ widget.data.label }}</p>
            <p class="text-3xl font-bold text-gray-900 mt-2">
                {{ widget.data.value }}
                <span class="text-lg font-normal text-gray-600">{{ widget.data.unit }}</span>
            </p>
        </div>
        <div class="flex-shrink-0">
            {% if 'oee' in widget.data.label.lower() %}
            <div class="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center">
                <svg class="w-8 h-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
                </svg>
            </div>
            {% elif 'production' in widget.data.label.lower() %}
            <div class="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center">
                <svg class="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z"></path>
                </svg>
            </div>
            {% elif 'downtime' in widget.data.label.lower() %}
            <div class="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center">
                <svg class="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>
            </div>
            {% else %}
            <div class="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center">
                <svg class="w-8 h-8 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"></path>
                </svg>
            </div>
            {% endif %}
        </div>
    </div>
</div>

html
<!-- app/templates/dashboard/widgets/table.html -->
<div class="bg-white rounded-lg shadow-md p-6">
    <h3 class="text-lg font-semibold text-gray-900 mb-4">
        Registro de Paradas
    </h3>
    <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    {% for column in widget.data.columns %}
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        {{ column }}
                    </th>
                    {% endfor %}
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                {% for row in widget.data.rows %}
                <tr class="hover:bg-gray-50">
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {{ row.start_time }}
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {{ row.end_time }}
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        {{ row.duration }}
                    </td>
                    <td class="px-6 py-4 text-sm text-gray-600">
                        {{ row.reason }}
                    </td>
                </tr>
                {% endfor %}
                
                {% if widget.data.rows | length == 0 %}
                <tr>
                    <td colspan="{{ widget.data.columns | length }}" 
                        class="px-6 py-4 text-center text-sm text-gray-500">
                        No se registraron paradas en el período seleccionado
                    </td>
                </tr>
                {% endif %}
            </tbody>
        </table>
    </div>
</div>

7.6 Grid de Widgets Dinámico
html
<!-- app/templates/dashboard/widgets_grid.html -->
<div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
    {% for widget_config in layout.grid %}
        {% set widget_data = widgets[loop.index0] %}
        
        <!-- Determinar el tamaño según la configuración -->
        <div class="
            {% if widget_config.w >= 8 %}col-span-full{% elif widget_config.w >= 6 %}md:col-span-2{% else %}md:col-span-1{% endif %}
        ">
            {% include "dashboard/widgets/" + widget_data.widget_type + ".html" %}
        </div>
    {% endfor %}
</div>

Deliverables FASE 7:
Sistema de templates Jinja2 completo
Panel de filtros dinámico con HTMX
6 widgets visuales implementados
Dashboard responsivo (mobile, tablet, desktop)
Optimización de recursos (CSS/JS minificados)

FASE 8: Seguridad OWASP (Semana 8-9)
Objetivos:
✅ Implementar OWASP Top 10 2021
✅ Audit logging completo
✅ Rate limiting robusto
✅ Tests de penetración básicos
Tareas Detalladas:
8.1 Security Headers Middleware
python
# app/middleware/security_headers.py
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        
        # OWASP Recommended Headers
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: https:; "
            "font-src 'self' https://fonts.gstatic.com; "
            "connect-src 'self'"
        )
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
        return response

8.2 Rate Limiting
python
# app/middleware/rate_limit.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)

# En app/main.py
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Uso en endpoints
@router.post("/auth/login")
@limiter.limit("5/minute")  # Máximo 5 intentos por minuto
async def login(request: Request, credentials: LoginRequest):
    # ...
    pass

@router.get("/data/detections")
@limiter.limit("100/minute")  # Máximo 100 consultas por minuto
async def get_detections(request: Request):
    # ...
    pass

8.3 SQL Injection Prevention
python
# app/services/detection_service.py
from sqlalchemy import text

class DetectionService:
    async def get_detections_safe(self, filters: QueryFilters):
        """
        CORRECTO: Usar parámetros vinculados
        """
        query = text("""
            SELECT * FROM detection_line_:line_id
            WHERE detected_at BETWEEN :start AND :end
            AND product_id = :product_id
        """)
        
        # SQLAlchemy escapa automáticamente los parámetros
        result = await self.db.execute(
            query,
            {
                'line_id': filters.line_id,
                'start': filters.start_date,
                'end': filters.end_date,
                'product_id': filters.product_id
            }
        )
        
        return result.fetchall()
    
    # NUNCA hacer esto:
    # query = f"SELECT * FROM detection WHERE product_id = {user_input}"

8.4 XSS Protection en Templates
html
<!-- Jinja2 escapa automáticamente por defecto -->
<p>Usuario: {{ user.username }}</p>  <!-- SEGURO -->

<!-- Si necesitas HTML sin escapar (usar con EXTREMA precaución) -->
<div>{{ content | safe }}</div>  <!-- PELIGROSO, validar primero -->

<!-- Mejor: sanitizar con Bleach antes de guardar en DB -->

python
# app/utils/sanitizers.py
import bleach

def sanitize_html(content: str) -> str:
    """
    Sanitiza HTML permitiendo solo tags seguros
    """
    allowed_tags = ['p', 'br', 'strong', 'em', 'ul', 'ol', 'li']
    allowed_attrs = {}
    
    return bleach.clean(
        content,
        tags=allowed_tags,
        attributes=allowed_attrs,
        strip=True


8.5 CSRF Protection
python
# Ya implementado con Flask-WTF
# En Flask:
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect(app)

# En templates:
<form method="POST">
    {{ csrf_token() }}
    <!-- ... -->
</form>

# Para HTMX:
<script>
document.body.addEventListener('htmx:configRequest', (event) => {
    event.detail.headers['X-CSRFToken'] = '{{ csrf_token() }}';
});
</script>

8.6 Password Hashing
python
# app/core/security.py
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def hash_password(password: str) -> str:
    """
    Hash de password con Argon2
    """
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica password contra hash
    """
    return pwd_context.verify(plain_password, hashed_password)

8.7 JWT Security
python
# app/core/security.py
from jose import JWTError, jwt
from datetime import datetime, timedelta

SECRET_KEY = os.getenv("SECRET_KEY")  # Debe ser fuerte y único
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

def create_access_token(data: dict) -> str:
    to_encode = data.copy()

8.8 Audit Logging Service
python
# app/services/audit_service.py
class AuditService:
    async def log_action(
        self,
        user_id: int,
        action: str,
        ip_address: str,
        details: dict,
        db: AsyncSession
    ):
        """
        Registra acciones en AUDIT_LOG
        """
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            ip_address=ip_address,
            details=details,
            created_at=datetime.utcnow()
        )
        
        db.add(audit_log)
        await db.commit()
    
    async def log_query(
        self,
        user_id: int,
        username: str,
        query_params: dict,
        db: AsyncSession
    ):
        """
        Registra consultas en USER_QUERY para auditoría
        """
        user_query = UserQuery(
            user_id=user_id,
            username=username,
            sql_query=query_params.get('sql', ''),
            query_parameters=json.dumps(query_params),
            start_date=query_params.get('start_date'),
            end_date=query_params.get('end_date'),
            line=query_params.get('line_id'),
            interval_type=query_params.get('interval'),
            created_at=datetime.utcnow()
        )
        
        db.add(user_query)
        await db.commit()

8.9 Input Validation con Pydantic
python
# app/schemas/query.py
from pydantic import BaseModel, validator, Field
from datetime import datetime
from typing import Optional, List

class QueryFilters(BaseModel):
    line_id: int = Field(..., gt=0)
    start_date: datetime
    end_date: datetime
    interval: str = Field(default='15min', regex='^(1min|15min|1hour|1day|1week|1month)$')
    shift_id: Optional[int] = Field(None, gt=0)
    product_ids: Optional[List[int]] = None
    
    @validator('end_date')
    def end_after_start(cls, v, values):
        if 'start_date' in values and v <= values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v
    
    @validator('start_date', 'end_date')
    def not_future(cls, v):
        if v > datetime.utcnow():
            raise ValueError('Date cannot be in the future')
        return v
    
    @validator('product_ids', pre=True)
    def parse_product_ids(cls, v):
        if v is None or v == '':
            return None
        if isinstance(v, str):
            return [int(x) for x in v.split(',') if x.strip()]
        return v

8.10 Session Management
# app/core/config.py
class Settings(BaseSettings):
    # Session
    SESSION_TIMEOUT_MINUTES: int = 30
    SESSION_REFRESH_THRESHOLD_MINUTES: int = 5
    MAX_CONCURRENT_SESSIONS: int = 3

# app/services/session_service.py
class SessionService:
    async def create_session(
        self,
        user_id: int,
        ip_address: str,
        user_agent: str,
        db: AsyncSession
    ) -> str:
        """
        Crea sesión y retorna session_id
        """
        # Verificar límite de sesiones concurrentes
        active_sessions = await self.get_active_sessions(user_id, db)
        
        if len(active_sessions) >= MAX_CONCURRENT_SESSIONS:
            # Cerrar la sesión más antigua
            await self.close_session(active_sessions[0].login_id, db)
        
        # Crear nueva sesión
        session = UserLogin(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            login_at=datetime.utcnow(),
            created_at=datetime.utcnow()
        )
        
        db.add(session)
        await db.commit()
        
        return str(session.login_id)
    
    async def validate_session(
        self,
        session_id: str,
        db: AsyncSession
    ) -> bool:
        """
        Valida que la sesión esté activa y no haya expirado
        """
        try:
            session = await db.get(UserLogin, int(session_id))
        except ValueError:
            return False
        
        if not session or session.logout_at:
            return False
        
        # Verificar timeout
        time_elapsed = datetime.utcnow() - session.login_at
        if time_elapsed > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
            await self.close_session(session.login_id, db)
            return False
        
        # Auto-refresh si está cerca del timeout
        if time_elapsed > timedelta(minutes=SESSION_TIMEOUT_MINUTES - SESSION_REFRESH_THRESHOLD_MINUTES):
            session.login_at = datetime.utcnow()
            await db.commit()
        
        return True
    
    async def close_session(
        self,
        session_id: int,
        db: AsyncSession
    ):
        """
        Cierra una sesión
        """
        session = await db.get(UserLogin, session_id)
        if session:
            session.logout_at = datetime.utcnow()
            await db.commit()
    
    async def get_active_sessions(
        self,
        user_id: int,
        db: AsyncSession
    ) -> List[UserLogin]:
        """
        Obtiene sesiones activas del usuario
        """
        result = await db.execute(
            select(UserLogin)
            .where(UserLogin.user_id == user_id)
            .where(UserLogin.logout_at.is_(None))
            .order_by(UserLogin.login_at.asc())
        )
        return result.scalars().all()

8.11 Sensitive Data Protection
python
# app/utils/encryption.py
from cryptography.fernet import Fernet
import base64
import os

class DataEncryption:
    def __init__(self):
        key = os.getenv('ENCRYPTION_KEY')
        if not key:
            raise ValueError("ENCRYPTION_KEY not set")
        self.cipher = Fernet(key.encode())
    
    def encrypt(self, data: str) -> str:
        """
        Encripta datos sensibles
        """
        return self.cipher.encrypt(data.encode()).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        Desencripta datos
        """
        return self.cipher.decrypt(encrypted_data.encode()).decode()

# Uso para datos sensibles en JSON
# Por ejemplo: config_tenant puede contener API keys

8.12 Environment Variables Security
python
# .env.example (NO incluir valores reales)
# Base de Datos Global
DB_GLOBAL_HOST=localhost
DB_GLOBAL_PORT=3306
DB_GLOBAL_NAME=dashboard_global
DB_GLOBAL_USER=your_user
DB_GLOBAL_PASSWORD=your_password

# Base de Datos Cliente (template)
DB_CLIENT_HOST=localhost
DB_CLIENT_PORT=3306

# Security
SECRET_KEY=generate_with_secrets.token_urlsafe(32)
ENCRYPTION_KEY=generate_with_Fernet.generate_key()
ALGORITHM=HS256

# Session
SESSION_TIMEOUT_MINUTES=30
MAX_CONCURRENT_SESSIONS=3

# CORS
ALLOWED_ORIGINS=http://localhost:5000,http://localhost:8000

# Rate Limiting
RATE_LIMIT_PER_MINUTE=100

# Logs
LOG_LEVEL=INFO
LOG_FILE=logs/dashboard.log

# Environment
ENV=development
DEBUG=True

8.13 HTTPS Enforcement
python
# app/middleware/https_redirect.py
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse

class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Solo en producción
        if os.getenv('ENV') == 'production':
            if request.url.scheme != 'https':
                url = request.url.replace(scheme='https')
                return RedirectResponse(url, status_code=301)
        
        return await call_next(request)

8.14 Security Testing
python
# tests/test_security.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_sql_injection_prevention(client: AsyncClient):
    """
    Test que intenta SQL injection
    """
    malicious_input = "1 OR 1=1; DROP TABLE users;--"
    
    response = await client.post("/api/v1/data/detections", json={
        "line_id": malicious_input,
        "start_date": "2024-01-01T00:00:00",
        "end_date": "2024-01-02T00:00:00"
    })
    
    # Debe fallar por validación de tipo
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_xss_prevention(client: AsyncClient):
    """
    Test que intenta XSS
    """
    malicious_script = "<script>alert('XSS')</script>"
    
    response = await client.post("/api/v1/users", json={
        "username": malicious_script,
        "email": "test@test.com",
        "password": "Test123!"
    })
    
    # Si se permite crear, verificar que se escapó
    if response.status_code == 201:
        user = response.json()
        assert "<script>" not in user['username']

@pytest.mark.asyncio
async def test_csrf_protection(client: AsyncClient):
    """
    Test de protección CSRF
    """
    # Intento sin CSRF token
    response = await client.post("/api/v1/production/lines", json={
        "line_name": "Test Line"
    })
    
    # Debe rechazar
    assert response.status_code in [403, 422]

@pytest.mark.asyncio
async def test_rate_limiting(client: AsyncClient):
    """
    Test de rate limiting
    """
    # Hacer múltiples requests rápidos
    responses = []
    for _ in range(150):  # Exceder límite de 100/min
        response = await client.get("/api/v1/production/lines")
        responses.append(response)
    
    # Alguno debe ser rechazado
    assert any(r.status_code == 429 for r in responses)

@pytest.mark.asyncio
async def test_password_strength(client: AsyncClient):
    """
    Test de contraseñas débiles
    """
    weak_passwords = ["123", "password", "qwerty", "abc123"]
    
    for weak_pass in weak_passwords:
        response = await client.post("/api/v1/users", json={
            "username": "testuser",
            "email": "test@test.com",
            "password": weak_pass
        })
        
        # Debe rechazar contraseñas débiles
        assert response.status_code == 422

Deliverables FASE 8:
OWASP Top 10 implementado completamente
Rate limiting funcional por IP y usuario
Audit logging completo de todas las acciones críticas
Session management con timeout y límite de sesiones
Tests de seguridad automatizados
Documento de mejores prácticas de seguridad

FASE 9: Optimización y Performance (Semana 9-10)
Objetivos:
✅ Optimizar queries de base de datos
✅ Implementar particionamiento automático
✅ Cache eficiente con actualización inteligente
✅ Monitoreo de performance
Tareas Detalladas:
9.1 Índices de Base de Datos
sql
-- Script de optimización para DB_CLIENT
-- scripts/optimize_db.sql

-- PRODUCTION_LINE
CREATE INDEX idx_line_active ON PRODUCTION_LINE(is_active);

-- AREA
CREATE INDEX idx_area_line ON AREA(line_id);
CREATE INDEX idx_area_type ON AREA(area_type);

-- PRODUCT
CREATE INDEX idx_product_code ON PRODUCT(product_code);

-- DETECTION_LINE_X (aplicar a cada tabla dinámica)
CREATE INDEX idx_detection_time ON detection_line_1(detected_at);
CREATE INDEX idx_detection_area ON detection_line_1(area_id);
CREATE INDEX idx_detection_product ON detection_line_1(product_id);
CREATE INDEX idx_detection_composite ON detection_line_1(detected_at, area_id, product_id);

-- DOWNTIME_EVENTS_X
CREATE INDEX idx_downtime_time ON downtime_events_1(start_time, end_time);

-- USER_LOGIN
CREATE INDEX idx_login_user ON USER_LOGIN(user_id);
CREATE INDEX idx_login_time ON USER_LOGIN(login_at);

-- AUDIT_LOG
CREATE INDEX idx_audit_user ON AUDIT_LOG(user_id);
CREATE INDEX idx_audit_time ON AUDIT_LOG(created_at);
CREATE INDEX idx_audit_action ON AUDIT_LOG(action);

-- USER_QUERY
CREATE INDEX idx_query_user ON USER_QUERY(user_id);
CREATE INDEX idx_query_time ON USER_QUERY(created_at);

9.2 Particionamiento Automático
python
# app/utils/partition_manager.py
from sqlalchemy import text
from datetime import datetime, timedelta
from typing import List

class PartitionManager:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_detection_table_with_partitions(
        self,
        line_id: int,
        start_date: datetime = None
    ):
        """
        Crea tabla DETECTION_LINE_X con particionamiento mensual
        """
        if not start_date:
            start_date = datetime.now().replace(day=1)
        
        # Crear tabla base
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS detection_line_{line_id} (
            detection_id INT AUTO_INCREMENT,
            detected_at TIMESTAMP NOT NULL,
            area_id INT NOT NULL,
            product_id INT NOT NULL,
            PRIMARY KEY (detection_id, detected_at),
            INDEX idx_detected_at (detected_at),
            INDEX idx_area_product (area_id, product_id)
        ) ENGINE=InnoDB
        PARTITION BY RANGE (YEAR(detected_at) * 100 + MONTH(detected_at)) (
        """
        
        # Crear particiones para los próximos 12 meses
        partitions = []
        current_date = start_date
        
        for i in range(12):
            year = current_date.year
            month = current_date.month
            partition_name = f"p{year}{month:02d}"
            
            # Calcular siguiente mes
            next_month = current_date + timedelta(days=32)
            next_month = next_month.replace(day=1)
            partition_value = next_month.year * 100 + next_month.month
            
            partitions.append(
                f"PARTITION {partition_name} VALUES LESS THAN ({partition_value})"
            )
            
            current_date = next_month
        
        # Agregar partición MAXVALUE
        partitions.append("PARTITION pmax VALUES LESS THAN MAXVALUE")
        
        create_table_sql += ",\n".join(partitions) + "\n);"
        
        await self.db.execute(text(create_table_sql))
        await self.db.commit()
    
    async def add_future_partition(
        self,
        line_id: int,
        year: int,
        month: int
    ):
        """
        Agrega una nueva partición para un mes futuro
        """
        partition_name = f"p{year}{month:02d}"
        
        # Calcular siguiente mes
        if month == 12:
            next_year = year + 1
            next_month = 1
        else:
            next_year = year
            next_month = month + 1
        
        partition_value = next_year * 100 + next_month
        
        # Verificar si la partición ya existe
        check_sql = f"""
        SELECT PARTITION_NAME 
        FROM INFORMATION_SCHEMA.PARTITIONS 
        WHERE TABLE_NAME = 'detection_line_{line_id}' 
        AND PARTITION_NAME = '{partition_name}'
        """
        
        result = await self.db.execute(text(check_sql))
        exists = result.fetchone()
        
        if not exists:
            # Reorganizar partición MAXVALUE
            alter_sql = f"""
            ALTER TABLE detection_line_{line_id}
            REORGANIZE PARTITION pmax INTO (
                PARTITION {partition_name} VALUES LESS THAN ({partition_value}),
                PARTITION pmax VALUES LESS THAN MAXVALUE
            )
            """
            
            await self.db.execute(text(alter_sql))
            await self.db.commit()
    
    async def drop_old_partitions(
        self,
        line_id: int,
        months_to_keep: int = 12
    ):
        """
        Elimina particiones antiguas (para gestión de almacenamiento)
        """
        cutoff_date = datetime.now() - timedelta(days=30 * months_to_keep)
        cutoff_value = cutoff_date.year * 100 + cutoff_date.month
        
        # Obtener particiones existentes
        get_partitions_sql = f"""
        SELECT PARTITION_NAME, PARTITION_DESCRIPTION
        FROM INFORMATION_SCHEMA.PARTITIONS
        WHERE TABLE_NAME = 'detection_line_{line_id}'
        AND PARTITION_NAME != 'pmax'
        ORDER BY PARTITION_DESCRIPTION
        """
        
        result = await self.db.execute(text(get_partitions_sql))
        partitions = result.fetchall()
        
        for partition in partitions:
            partition_name = partition[0]
            partition_value = int(partition[1])
            
            if partition_value < cutoff_value:
                # Eliminar partición
                drop_sql = f"""
                ALTER TABLE detection_line_{line_id}
                DROP PARTITION {partition_name}
                """
                
                await self.db.execute(text(drop_sql))
                await self.db.commit()
                
                print(f"Dropped partition {partition_name} from detection_line_{line_id}")

9.3 Background Task para Mantenimiento de Particiones
python
# app/tasks/partition_maintenance.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job('cron', day=1, hour=2)  # Primer día del mes a las 2 AM
async def maintain_partitions():
    """
    Mantenimiento mensual de particiones
    """
    db = get_db_session()
    partition_manager = PartitionManager(db)
    
    # Obtener todas las líneas activas
    result = await db.execute(
        select(ProductionLine).where(ProductionLine.is_active == True)
    )
    active_lines = result.scalars().all()
    
    # Para cada línea
    for line in active_lines:
        # Crear partición para los próximos 2 meses
        future_date = datetime.now() + timedelta(days=60)
        
        await partition_manager.add_future_partition(
            line_id=line.line_id,
            year=future_date.year,
            month=future_date.month
        )
        
        # Eliminar particiones antiguas (mantener 12 meses)
        await partition_manager.drop_old_partitions(
            line_id=line.line_id,
            months_to_keep=12
        )
    
    await db.close()

9.4 Query Optimization
python
# app/services/detection_service.py
class DetectionService:
    async def get_detections_optimized(
        self,
        filters: QueryFilters
    ) -> pd.DataFrame:
        """
        Query optimizado con hint de particiones
        """
        # Calcular particiones necesarias
        partitions = self._get_partition_names(
            filters.start_date,
            filters.end_date
        )
        
        # Query con PARTITION hint
        partition_hint = f"PARTITION ({','.join(partitions)})" if partitions else ""
        
        query = f"""
        SELECT 
            detection_id,
            detected_at,
            area_id,
            product_id
        FROM detection_line_{filters.line_id} {partition_hint}
        WHERE detected_at BETWEEN :start AND :end
        """
        
        # Agregar filtros opcionales
        params = {
            'start': filters.start_date,
            'end': filters.end_date
        }
        
        if filters.area_ids:
            query += " AND area_id IN :areas"
            params['areas'] = tuple(filters.area_ids)
        
        if filters.product_ids:
            query += " AND product_id IN :products"
            params['products'] = tuple(filters.product_ids)
        
        # Ejecutar con parámetros
        result = await self.db.execute(text(query), params)
        rows = result.fetchall()
        
        # Convertir a DataFrame
        df = pd.DataFrame(rows, columns=['detection_id', 'detected_at', 'area_id', 'product_id'])
        
        # Enriquecer con cache (app-side join)
        df['area_name'] = df['area_id'].map(
            lambda x: self.cache.get_area(x)['area_name']
        )
        df['product_name'] = df['product_id'].map(
            lambda x: self.cache.get_product(x)['product_name']
        )
        
        return df
    
    def _get_partition_names(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[str]:
        """
        Calcula nombres de particiones necesarias para el rango
        """
        partitions = []
        current_date = start_date.replace(day=1)
        
        while current_date <= end_date:
            partition_name = f"p{current_date.year}{current_date.month:02d}"
            partitions.append(partition_name)
            
            # Siguiente mes
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)
        
        return partitions

9.5 Cache Optimization
python
# app/core/cache.py
from functools import lru_cache
from typing import Dict, Optional
import asyncio

class MetadataCache:
    def __init__(self):
        self._cache: Dict[int, Dict] = {
            'products': {},
            'areas': {},
            'lines': {},
            'filters': {},
            'shifts': {}
        }
        self._lock = asyncio.Lock()
        self._last_updated: Optional[datetime] = None
        self._ttl_seconds = 3600  # 1 hora
    
    async def load_metadata(self, tenant_id: int, db: AsyncSession):
        """
        Carga inicial de metadatos
        """
        async with self._lock:
            # Products
            result = await db.execute(select(Product))
            products = result.scalars().all()
            self._cache['products'] = {
                p.product_id: {
                    'product_name': p.product_name,
                    'product_code': p.product_code,
                    'product_weight': float(p.product_weight),
                    'product_color': p.product_color
                }
                for p in products
            }
            
            # Areas
            result = await db.execute(select(Area))
            areas = result.scalars().all()
            self._cache['areas'] = {
                a.area_id: {
                    'area_name': a.area_name,
                    'line_id': a.line_id,
                    'area_type': a.area_type,
                    'area_order': a.area_order
                }
                for a in areas
            }
            
            # Production Lines
            result = await db.execute(select(ProductionLine))
            lines = result.scalars().all()
            self._cache['lines'] = {
                l.line_id: {
                    'line_name': l.line_name,
                    'line_code': l.line_code,
                    'availability': l.availability,
                    'performance': l.performance,
                    'downtime_threshold': l.downtime_threshold
                }
                for l in lines
            }
            
            # Filters
            result = await db.execute(select(Filter).where(Filter.filter_status == True))
            filters = result.scalars().all()
            self._cache['filters'] = {
                f.filter_id: {
                    'filter_name': f.filter_name,
                    'default_value': f.default_value,
                    'additional_filter': f.additional_filter
                }
                for f in filters
            }
            
            # Shifts
            result = await db.execute(select(Shift).where(Shift.shift_status == True))
            shifts = result.scalars().all()
            self._cache['shifts'] = {
                s.shift_id: {
                    'shift_name': s.shift_name,
                    'days_implemented': s.days_implemented,
                    'start_time': s.start_time,
                    'end_time': s.end_time,
                    'is_overnight': s.is_overnight
                }
                for s in shifts
            }
            
            self._last_updated = datetime.utcnow()
    
    def get_product(self, product_id: int) -> Dict:
        """
        Obtiene producto del cache
        """
        return self._cache['products'].get(product_id, {})
    
    def get_area(self, area_id: int) -> Dict:
        """
        Obtiene área del cache
        """
        return self._cache['areas'].get(area_id, {})
    
    def get_line(self, line_id: int) -> Dict:
        """
        Obtiene línea del cache
        """
        return self._cache['lines'].get(line_id, {})
    
    def get_all_lines(self) -> Dict:
        """
        Obtiene todas las líneas
        """
        return self._cache['lines']
    
    async def needs_refresh(self) -> bool:
        """
        Verifica si el cache necesita actualizarse
        """
        if not self._last_updated:
            return True
        
        time_elapsed = datetime.utcnow() - self._last_updated
        return time_elapsed.total_seconds() > self._ttl_seconds
    
    async def refresh_if_needed(self, tenant_id: int, db: AsyncSession):
        """
        Refresca cache si es necesario
        """
        if await self.needs_refresh():
            await self.load_metadata(tenant_id, db)
    
    def invalidate(self):
        """
        Invalida el cache forzando recarga
        """
        self._last_updated = None

9.6 Database Connection Pooling
python
# app/core/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool, QueuePool

class DatabaseManager:
    def __init__(self):
        self.engines = {}
        self.session_makers = {}
    
    def get_engine(self, db_name: str, is_global: bool = False):
        """
        Obtiene o crea engine con connection pooling
        """
        if db_name not in self.engines:
            if is_global:
                db_url = f"mysql+aiomysql://{DB_GLOBAL_USER}:{DB_GLOBAL_PASSWORD}@{DB_GLOBAL_HOST}/{db_name}"
            else:
                db_url = f"mysql+aiomysql://{DB_CLIENT_USER}:{DB_CLIENT_PASSWORD}@{DB_CLIENT_HOST}/{db_name}"
            
            # Configuración de pool optimizada
            self.engines[db_name] = create_async_engine(
                db_url,
                poolclass=QueuePool,
                pool_size=10,          # Conexiones base
                max_overflow=20,       # Conexiones adicionales
                pool_timeout=30,       # Timeout para obtener conexión
                pool_recycle=3600,     # Reciclar conexiones cada hora
                pool_pre_ping=True,    # Verificar conexión antes de usar
                echo=False             # No loggear queries (en producción)
            )
            
            self.session_makers[db_name] = async_sessionmaker(
                self.engines[db_name],
                class_=AsyncSession,
                expire_on_commit=False
            )
        
        return self.engines[db_name]
    
    async def get_session(self, db_name: str, is_global: bool = False):
        """
        Obtiene sesión de base de datos
        """
        if db_name not in self.session_makers:
            self.get_engine(db_name, is_global)
        
        async with self.session_makers[db_name]() as session:
            yield session

9.7 Performance Monitoring
python
# app/middleware/performance_monitor.py
import time
from starlette.middleware.base import BaseHTTPMiddleware
import logging

logger = logging.getLogger(__name__)

class PerformanceMonitorMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start_time = time.time()
        
        response = await call_next(request)
        
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        
        # Log queries lentas (> 1 segundo)
        if process_time > 1.0:
            logger.warning(
                f"Slow request: {request.method} {request.url.path} "
                f"took {process_time:.2f}s"
            )
        
        return response

9.8 Database Query Logger
python
# app/utils/query_logger.py
from sqlalchemy import event
from sqlalchemy.engine import Engine
import logging
import time

logger = logging.getLogger('sqlalchemy.queries')

@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault('query_start_time', []).append(time.time())

@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total_time = time.time() - conn.info['query_start_time'].pop()
    
    # Log queries lentas (> 500ms)
    if total_time > 0.5:
        logger.warning(
            f"Slow query ({total_time:.2f}s): {statement[:200]}..."
        )

Deliverables FASE 9:
Índices de base de datos optimizados
Particionamiento automático funcionando
Connection pooling configurado
Cache con TTL e invalidación inteligente
Monitoreo de performance implementado
Queries optimizados (< 200ms promedio)

FASE 10: Deployment en cPanel (Semana 10-11)
Objetivos:
✅ Configurar entorno de producción
✅ Deploy de FastAPI + Flask
✅ Configuración de WSGI
✅ Automatización de backups
Tareas Detalladas:
10.1 Configuración de cPanel
bash
# 1. Crear estructura de directorios en cPanel
/home/usuario/
├── public_html/           # No usar para la app
├── dashboard-saas/        # Aplicación principal
│   ├── app/
│   ├── migrations/
│   ├── scripts/
│   ├── .env.production
│   ├── requirements.txt
│   └── passenger_wsgi.py
├── logs/
│   ├── dashboard.log
│   ├── error.log
│   └── access.log
└── backups/

10.2 Passenger WSGI Configuration
python
# passenger_wsgi.py
import sys
import os

# Agregar path de la aplicación
sys.path.insert(0, os.path.dirname(__file__))

# Cargar variables de entorno
from dotenv import load_dotenv
load_dotenv('.env.production')

# Importar aplicación Flask
from app.wsgi import app as application

# Para FastAPI (si usas Passenger)
# from app.main import app as application

10.3 Setup Script
bash
# scripts/setup_production.sh
#!/bin/bash

echo "Setting up Dashboard SaaS in production..."

# 1. Crear virtual environment
python3.11 -m venv venv
source venv/bin/activate

# 2. Instalar dependencias
pip install --upgrade pip
pip install -r requirements.txt

# 3. Crear directorios necesarios
mkdir -p logs
mkdir -p backups
mkdir -p static/css
mkdir -p static/js

# 4. Copiar .env template
if [ ! -f .env.production ]; then
    cp .env.example .env.production
    echo "⚠️  Configure .env.production before continuing"
    exit 1
fi

# 5. Inicializar base de datos
python scripts/init_db.py

# 6. Crear particiones iniciales
python scripts/create_partitions.py

# 7. Configurar permisos
chmod 755 passenger_wsgi.py
chmod -R 755 app/
chmod -R 777 logs/
chmod -R 755 static/

# 8. Compilar assets estáticos (si es necesario)
# npm run build  # Si usas compilación de CSS/JS

echo "✓ Setup completed successfully!"
echo "Next steps:"
echo "1. Configure .env.production with your database credentials"
echo "2. Update passenger_wsgi.py if needed"
echo "3. Restart the application from cPanel"

10.4 Database Initialization Script
python
# scripts/init_db.py
import asyncio
import sys
import os

# Agregar path del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.database import DatabaseManager
from app.models.base import Base
from app.models.global_db import Tenant, User, AuditLog, UserLogin, UserQuery, DashboardTemplate, WidgetCatalog
from app.models.client_db import ProductionLine, Area, Product, Filter, Shift, Failure, Incident, SystemConfig
from app.core.security import hash_password
from sqlalchemy import text
from datetime import datetime

async def init_global_db():
    """
    Inicializa base de datos global con tablas y datos iniciales
    """
    print("Initializing Global Database...")
    
    db_manager = DatabaseManager()
    engine = db_manager.get_engine('dashboard_global', is_global=True)
    
    # Crear tablas
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Insertar datos iniciales
    async for session in db_manager.get_session('dashboard_global', is_global=True):
        # Crear tenant de prueba
        tenant = Tenant(
            company_name="Demo Company",
            asociated_since=datetime.utcnow(),
            is_active=True,
            config_tenant={"theme": "default"}
        )
        session.add(tenant)
        await session.commit()
        
        # Crear usuario administrador
        admin_user = User(
            tenant_id=tenant.tenant_id,
            username="admin",
            email="admin@demo.com",
            password=hash_password("Admin123!"),
            role="admin",
            permissions={"full_access": True},
            created_at=datetime.utcnow()
        )
        session.add(admin_user)
        
        # Crear catálogo de widgets
        widgets = [
            WidgetCatalog(
                widget_name="Producción por Tiempo",
                widget_type="line_chart",
                required_params={
                    "type": "object",
                    "properties": {
                        "line_id": {"type": "integer"},
                        "start_date": {"type": "string", "format": "date-time"},
                        "end_date": {"type": "string", "format": "date-time"},
                        "interval": {"type": "string", "enum": ["1min", "15min", "1hour", "1day", "1week", "1month"]}
                    },
                    "required": ["line_id", "start_date", "end_date"]
                }
            ),
            WidgetCatalog(
                widget_name="Distribución de Productos",
                widget_type="pie_chart",
                required_params={
                    "type": "object",
                    "properties": {
                        "line_id": {"type": "integer"},
                        "start_date": {"type": "string", "format": "date-time"},
                        "end_date": {"type": "string", "format": "date-time"}
                    },
                    "required": ["line_id", "start_date", "end_date"]
                }
            ),
            WidgetCatalog(
                widget_name="Comparación Entrada/Salida",
                widget_type="bar_chart",
                required_params={
                    "type": "object",
                    "properties": {
                        "line_id": {"type": "integer"},
                        "start_date": {"type": "string", "format": "date-time"},
                        "end_date": {"type": "string", "format": "date-time"}
                    },
                    "required": ["line_id", "start_date", "end_date"]
                }
            ),
            WidgetCatalog(
                widget_name="KPI OEE",
                widget_type="kpi_card",
                required_params={
                    "type": "object",
                    "properties": {
                        "line_id": {"type": "integer"},
                        "start_date": {"type": "string", "format": "date-time"},
                        "end_date": {"type": "string", "format": "date-time"},
                        "kpi_type": {"type": "string", "enum": ["oee"]}
                    },
                    "required": ["line_id", "start_date", "end_date", "kpi_type"]
                }
            ),
            WidgetCatalog(
                widget_name="Tabla de Paradas",
                widget_type="table",
                required_params={
                    "type": "object",
                    "properties": {
                        "line_id": {"type": "integer"},
                        "start_date": {"type": "string", "format": "date-time"},
                        "end_date": {"type": "string", "format": "date-time"}
                    },
                    "required": ["line_id", "start_date", "end_date"]
                }
            )
        ]
        
        for widget in widgets:
            session.add(widget)
        
        await session.commit()
        
        print(f"✓ Global DB initialized")
        print(f"  - Tenant created: {tenant.company_name} (ID: {tenant.tenant_id})")
        print(f"  - Admin user: {admin_user.username}")
        print(f"  - Widgets catalog: {len(widgets)} widgets")

async def init_client_db(tenant_id: int, db_name: str):
    """
    Inicializa base de datos de cliente con estructura y datos de ejemplo
    """
    print(f"\nInitializing Client Database '{db_name}' for tenant {tenant_id}...")
    
    db_manager = DatabaseManager()
    engine = db_manager.get_engine(db_name, is_global=False)
    
    # Crear tablas
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Insertar datos de ejemplo
    async for session in db_manager.get_session(db_name, is_global=False):
        # Crear línea de producción
        line = ProductionLine(
            line_name="Línea Principal",
            line_code="LP01",
            is_active=True,
            availability=95,
            performance=85,
            downtime_threshold=300,  # 5 minutos en segundos
            created_at=datetime.utcnow()
        )
        session.add(line)
        await session.commit()
        
        # Crear áreas
        areas = [
            Area(
                line_id=line.line_id,
                area_name="Entrada",
                area_type="input",
                area_order=1,
                coord_x1=0, coord_y1=0,
                coord_x2=100, coord_y2=100,
                created_at=datetime.utcnow()
            ),
            Area(
                line_id=line.line_id,
                area_name="Proceso",
                area_type="process",
                area_order=2,
                coord_x1=100, coord_y1=0,
                coord_x2=200, coord_y2=100,
                created_at=datetime.utcnow()
            ),
            Area(
                line_id=line.line_id,
                area_name="Salida",
                area_type="output",
                area_order=3,
                coord_x1=200, coord_y1=0,
                coord_x2=300, coord_y2=100,
                created_at=datetime.utcnow()
            )
        ]
        
        for area in areas:
            session.add(area)
        
        # Crear productos
        products = [
            Product(
                product_name="Producto A",
                product_code="PA001",
                product_weight=5.5,
                product_color="Rojo",
                production_std=100,
                product_per_batch=50
            ),
            Product(
                product_name="Producto B",
                product_code="PB001",
                product_weight=3.2,
                product_color="Azul",
                production_std=120,
                product_per_batch=60
            )
        ]
        
        for product in products:
            session.add(product)
        
        # Crear turnos
        shifts = [
            Shift(
                shift_name="Turno Mañana",
                description="Turno de 7:00 a 15:00",
                shift_status=True,
                days_implemented=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                start_time="07:00:00",
                end_time="15:00:00",
                is_overnight=False,
                created_at=datetime.utcnow()
            ),
            Shift(
                shift_name="Turno Tarde",
                description="Turno de 15:00 a 23:00",
                shift_status=True,
                days_implemented=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                start_time="15:00:00",
                end_time="23:00:00",
                is_overnight=False,
                created_at=datetime.utcnow()
            ),
            Shift(
                shift_name="Turno Noche",
                description="Turno de 23:00 a 7:00",
                shift_status=True,
                days_implemented=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                start_time="23:00:00",
                end_time="07:00:00",
                is_overnight=True,
                created_at=datetime.utcnow()
            )
        ]
        
        for shift in shifts:
            session.add(shift)
        
        # Crear filtros
        filters = [
            Filter(
                filter_name="Rango de Fechas",
                description="Filtro de fecha inicio y fin",
                filter_status=True,
                default_value={"days_back": 7},
                additional_filter={},
                created_at=datetime.utcnow()
            ),
            Filter(
                filter_name="Intervalo",
                description="Intervalo de agregación",
                filter_status=True,
                default_value={"interval": "15min"},
                additional_filter={},
                created_at=datetime.utcnow()
            )
        ]
        
        for f in filters:
            session.add(f)
        
        await session.commit()
        
        print(f"✓ Client DB '{db_name}' initialized")
        print(f"  - Production Line: {line.line_name}")
        print(f"  - Areas: {len(areas)}")
        print(f"  - Products: {len(products)}")
        print(f"  - Shifts: {len(shifts)}")
        
        return line.line_id

async def create_detection_table(db_name: str, line_id: int):
    """
    Crea tabla de detecciones con particionamiento
    """
    from app.utils.partition_manager import PartitionManager
    
    db_manager = DatabaseManager()
    async for session in db_manager.get_session(db_name, is_global=False):
        partition_manager = PartitionManager(session)
        await partition_manager.create_detection_table_with_partitions(line_id)
        print(f"✓ Detection table created for line {line_id} with partitions")

if __name__ == "__main__":
    async def main():
        # Inicializar DB Global
        await init_global_db()
        
        # Inicializar DB de Cliente de ejemplo
        client_db = "dashboard_client_1"
        line_id = await init_client_db(tenant_id=1, db_name=client_db)
        
        # Crear tabla de detecciones
        await create_detection_table(client_db, line_id)
        
        print("\n✓ All databases initialized successfully!")
    
    asyncio.run(main())

10.5 Backup Script
bash
# scripts/backup_db.sh
#!/bin/bash

# Configuración
BACKUP_DIR="/home/usuario/backups"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

# Crear directorio de backup si no existe
mkdir -p $BACKUP_DIR

# Cargar credenciales desde .env
source .env.production

echo "Starting backup process..."

# Backup de DB Global
echo "Backing up global database..."
mysqldump -h $DB_GLOBAL_HOST \
          -u $DB_GLOBAL_USER \
          -p$DB_GLOBAL_PASSWORD \
          $DB_GLOBAL_NAME > "$BACKUP_DIR/global_$DATE.sql"

if [ $? -eq 0 ]; then
    gzip "$BACKUP_DIR/global_$DATE.sql"
    echo "✓ Global DB backed up"
else
    echo "✗ Global DB backup failed"
    exit 1
fi

# Backup de DBs de Clientes (detectar automáticamente)
CLIENT_DBS=$(mysql -h $DB_CLIENT_HOST \
                  -u $DB_CLIENT_USER \
                  -p$DB_CLIENT_PASSWORD \
                  -e "SHOW DATABASES LIKE 'dashboard_client_%';" -s --skip-column-names)

for db in $CLIENT_DBS; do
    echo "Backing up client database: $db..."
    mysqldump -h $DB_CLIENT_HOST \
              -u $DB_CLIENT_USER \
              -p$DB_CLIENT_PASSWORD \
              $db > "$BACKUP_DIR/${db}_$DATE.sql"
    
    if [ $? -eq 0 ]; then
        gzip "$BACKUP_DIR/${db}_$DATE.sql"
        echo "✓ $db backed up"
    else
        echo "✗ $db backup failed"
    fi
done

# Limpiar backups antiguos
echo "Cleaning old backups (older than $RETENTION_DAYS days)..."
find $BACKUP_DIR -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete
echo "✓ Old backups cleaned"

echo "Backup process completed at $(date)"

10.6 Cron Jobs Configuration
bash
# Configurar en cPanel -> Cron Jobs

# Backup diario a las 3 AM
0 3 * * * /home/usuario/dashboard-saas/scripts/backup_db.sh >> /home/usuario/logs/backup.log 2>&1

# Mantenimiento de particiones (primer día del mes a las 2 AM)
0 2 1 * * cd /home/usuario/dashboard-saas && source venv/bin/activate && python -c "from app.tasks.partition_maintenance import maintain_partitions; import asyncio; asyncio.run(maintain_partitions())" >> /home/usuario/logs/partition_maintenance.log 2>&1

# Limpieza de logs antiguos (semanal)
0 4 * * 0 find /home/usuario/logs -name "*.log" -mtime +30 -delete

# Cálculo de paradas (cada 15 minutos)
*/15 * * * * cd /home/usuario/dashboard-saas && source venv/bin/activate && python -c "from app.tasks.downtime_calculator import auto_calculate_downtimes; import asyncio; asyncio.run(auto_calculate_downtimes())" >> /home/usuario/logs/downtime.log 2>&1

10.7 Nginx/Apache Configuration (via cPanel)
apache
# .htaccess (si usas Apache con Passenger)
PassengerEnabled On
PassengerAppRoot /home/usuario/dashboard-saas
PassengerPython /home/usuario/dashboard-saas/venv/bin/python
PassengerStartupFile passenger_wsgi.py

# Configuración de seguridad
<IfModule mod_headers.c>
    Header always set X-Frame-Options "DENY"
    Header always set X-Content-Type-Options "nosniff"
    Header always set X-XSS-Protection "1; mode=block"
    Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains"
</IfModule>

# Forzar HTTPS
RewriteEngine On
RewriteCond %{HTTPS} off
RewriteRule ^(.*)$ https://%{HTTP_HOST}%{REQUEST_URI} [L,R=301]

# Cachear archivos estáticos
<FilesMatch "\.(css|js|jpg|jpeg|png|gif|ico|svg|woff|woff2|ttf|eot)$">
    Header set Cache-Control "max-age=31536000, public"
</FilesMatch>

10.8 Health Check Endpoint
python
# app/api/v1/system.py
@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Endpoint de health check para monitoreo
    """
    try:
        # Verificar conexión a DB
        await db.execute(text("SELECT 1"))
        
        # Verificar cache
        cache_status = "ok" if cache_service.is_loaded() else "not_loaded"
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "database": "connected",
            "cache": cache_status,
            "version": "1.0.0"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@router.get("/metrics")
async def get_system_metrics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Métricas del sistema (solo admin)
    """
    if current_user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Obtener última entrada de SYSTEM_MONITOR
    result = await db.execute(
        select(SystemMonitor)
        .order_by(SystemMonitor.created_at.desc())
        .limit(1)
    )
    latest_metric = result.scalar_one_or_none()
    
    if not latest_metric:
        return {"message": "No metrics available"}
    
    return {
        "cpu_usage": latest_metric.cpu_usage,
        "ram_usage": latest_metric.ram_usage,
        "cpu_temp": latest_metric.cpu_temp,
        "timestamp": latest_metric.created_at.isoformat()
    }

10.9 Monitoring Script
python
# scripts/monitor_system.py
import psutil
import asyncio
from datetime import datetime
from app.core.database import DatabaseManager
from app.models.client_db.system import SystemMonitor

async def collect_metrics(db_name: str):
    """
    Recolecta métricas del sistema y las guarda en SYSTEM_MONITOR
    """
    # CPU
    cpu_usage = psutil.cpu_percent(interval=1)
    cpu_freq = psutil.cpu_freq().current if psutil.cpu_freq() else 0
    
    # RAM
    ram = psutil.virtual_memory()
    ram_usage = ram.percent
    ram_used_bytes = ram.used
    
    # Temperatura (si está disponible)
    try:
        temps = psutil.sensors_temperatures()
        cpu_temp = temps['coretemp'][0].current if 'coretemp' in temps else 0
    except:
        cpu_temp = 0
    
    # GPU (si está disponible - requiere pynvml para NVIDIA)
    gpu_name = None
    gpu_temp = None
    gpu_usage = None
    gpu_mem_used = None
    gpu_mem_total = None
    
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        gpu_name = pynvml.nvmlDeviceGetName(handle)
        gpu_temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
        gpu_util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        gpu_usage = gpu_util.gpu
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        gpu_mem_used = mem_info.used
        gpu_mem_total = mem_info.total
    except:
        pass
    
    # Guardar en DB
    db_manager = DatabaseManager()
    async for session in db_manager.get_session(db_name, is_global=False):
        metric = SystemMonitor(
            created_at=datetime.utcnow(),
            cpu_usage=cpu_usage,
            cpu_freq=int(cpu_freq),
            ram_usage=ram_usage,
            ram_used_bytes=ram_used_bytes,
            cpu_temp=int(cpu_temp),
            cpu_temp_sensor=cpu_temp,
            gpu_name=gpu_name,
            gpu_temp=gpu_temp,
            gpu_usage=gpu_usage,
            gpu_mem_used_bytes=gpu_mem_used,
            gpu_mem_total_bytes=gpu_mem_total
        )
        
        session.add(metric)
        await session.commit()
        
        print(f"✓ Metrics collected: CPU {cpu_usage}%, RAM {ram_usage}%")

if __name__ == "__main__":
    # Recolectar métricas para todos los clientes
    client_dbs = ["dashboard_client_1"]  # Cargar dinámicamente
    
    async def collect_all():
        for db in client_dbs:
            await collect_metrics(db)
    
    asyncio.run(collect_all())

10.10 Deployment Checklist
markdown
# Deployment Checklist

## Pre-Deployment
- [ ] .env.production configurado con credenciales reales
- [ ] SECRET_KEY y ENCRYPTION_KEY generados (seguros)
- [ ] Bases de datos creadas en cPanel MySQL
- [ ] Usuario de base de datos con permisos correctos
- [ ] Virtual environment creado y activado
- [ ] Dependencias instaladas (requirements.txt)

## Database Setup
- [ ] Script init_db.py ejecutado
- [ ] Tenant y usuario admin creados
- [ ] Widget catalog poblado
- [ ] Tablas de cliente inicializadas
- [ ] Particiones creadas para detecciones
- [ ] Índices aplicados

## Application Configuration
- [ ] passenger_wsgi.py configurado
- [ ] .htaccess configurado (si usa Apache)
- [ ] Permisos de archivos correctos (755/777)
- [ ] Static files accesibles
- [ ] Logs directory con permisos de escritura

## Security
- [ ] HTTPS configurado y funcionando
- [ ] Security headers en .htaccess
- [ ] CORS configurado correctamente
- [ ] Rate limiting activado
- [ ] Session timeout configurado
- [ ] Passwords hasheados con Argon2

## Cron Jobs
- [ ] Backup diario configurado
- [ ] Mantenimiento de particiones mensual
- [ ] Cálculo de paradas cada 15 min
- [ ] Limpieza de logs semanalmente

## Testing
- [ ] Health check endpoint funcional (/api/v1/system/health)
- [ ] Login funcional
- [ ] Dashboard carga correctamente
- [ ] Filtros y widgets funcionan
- [ ] Queries optimizadas (< 1s)
- [ ] No hay errores en logs

## Monitoring
- [ ] Error logging configurado
- [ ] Access logging habilitado
- [ ] System metrics recolectándose
- [ ] Alertas configuradas (si aplica)

## Documentation
- [ ] README.md actualizado
- [ ] Credenciales documentadas (en lugar seguro)
- [ ] Proceso de backup documentado
- [ ] Procedimiento de rollback definido

## Post-Deployment
- [ ] Backup inicial tomado
- [ ] Performance baseline establecido
- [ ] Usuarios de prueba creados
- [ ] Capacitación a usuarios admin

Deliverables FASE 10:
Aplicación desplegada y funcional en cPanel
Scripts de deployment automatizados
Backups configurados y probados
Cron jobs funcionando
Monitoreo de sistema activo
Documentación de deployment completa

📋 TODO List (Funcionalidades Futuras)
markdown
# TODO - Funcionalidades Futuras

## Retención de Datos Históricos
- [ ] Definir política de retención (6 meses, 1 año, 2 años)
- [ ] Implementar archivado automático de particiones antiguas
- [ ] Sistema de compresión de datos históricos
- [ ] Migración a almacenamiento frío (S3, etc.)

## Autenticación de Dos Factores (2FA)
- [ ] Integrar TOTP (Google Authenticator, Authy)
- [ ] SMS verification como opción
- [ ] Códigos de recuperación
- [ ] Configuración por usuario

## Reportes Avanzados
- [ ] Generación de PDF con gráficos
- [ ] Reportes programados (email diario/semanal)
- [ ] Exportación a Excel con formateo
- [ ] Comparación de períodos

## Alertas y Notificaciones
- [ ] Sistema de alertas configurables
- [ ] Notificaciones por email
- [ ] Webhook notifications
- [ ] Alertas de paradas prolongadas

## Multi-Planta
- [ ] Segmentación por planta
- [ ] Dashboard comparativo entre plantas
- [ ] Gestión centralizada multi-tenant

## Optimizaciones
- [ ] Implementar Redis para cache (si disponible)
- [ ] WebSocket para updates en tiempo real
- [ ] Lazy loading de widgets
- [ ] Server-sent events para notificaciones

## Machine Learning
- [ ] Predicción de paradas
- [ ] Detección de anomalías
- [ ] Optimización de producción con IA

## API Pública
- [ ] API REST documentada (OpenAPI/Swagger)
- [ ] Rate limiting por API key
- [ ] Webhooks para eventos
```

---

## 🎯 Resumen Ejecutivo de la Planificación

### Fases Completadas en la Planificación:

1. **FASE 1-2**: Fundaciones, Auth, Cache (Semanas 1-3)
2. **FASE 3-4**: Motor de Consultas, Cálculo de Paradas (Semanas 3-5)
3. **FASE 5-6**: Métricas KPIs, Motor de Widgets (Semanas 5-7)
4. **FASE 7**: Frontend Flask + Jinja2 + HTMX (Semanas 7-8)
5. **FASE 8**: Seguridad OWASP (Semanas 8-9)
6. **FASE 9**: Optimización y Performance (Semanas 9-10)
7. **FASE 10**: Deployment en cPanel (Semanas 10-11)

### Stack Tecnológico Final:
```
Backend:
- FastAPI (API REST)
- Flask (SSR con Jinja2)
- SQLAlchemy 2.0
- MySQL 8.0+
- APScheduler (background tasks)

Frontend:
- Jinja2 Templates
- HTMX
- Alpine.js
- Chart.js
- Tailwind CSS

Seguridad:
- Argon2 (password hashing)
- JWT (authentication)
- CSRF protection
- Rate limiting
- OWASP Top 10 compliance

Arquitectura de Bases de Datos:
DB_GLOBAL: Multitenancy central (TENANT, USER, AUDIT_LOG, DASHBOARD_TEMPLATE)
DB_CLIENT_{tenant_id}: Por cliente (PRODUCTION_LINE, AREA, PRODUCT, DETECTION_LINE_X)
Particionamiento: Mensual por RANGE en tablas de detecciones
Caché: In-memory para metadatos (PRODUCT, AREA, LINE)
Requirements
# ============================================================================
# Dashboard SaaS Industrial - Requirements
# Target: Python 3.12 (Stable)
# ============================================================================

# ============================================================================
# CORE FRAMEWORK
# ============================================================================
fastapi==0.110.0         # Actualizado: Mejoras de rendimiento y validación
uvicorn[standard]==0.29.0
python-multipart>=0.0.9  # CRÍTICO: Versión mínima para evitar warnings en 3.12

# Nota: Tienes Flask y FastAPI juntos. Si es una migración, está bien.
# Si es un proyecto nuevo, elige uno para no inflar la imagen de Docker.
flask==3.0.2

# ============================================================================
# DATABASE
# ============================================================================
sqlalchemy[asyncio]==2.0.29
aiomysql==0.2.0
alembic==1.13.1
asyncmy==0.2.9

# ============================================================================
# DATA PROCESSING
# ============================================================================
# Estas versiones compilan nativamente (wheels) en 3.12 sin problemas
pandas>=2.2.1
numpy>=1.26.4

# ============================================================================
# SECURITY & AUTHENTICATION
# ============================================================================
# Passlib funciona en 3.12, pero está "quieto".
# Si puedes, migra a pwdlib en el futuro.
passlib[argon2]==1.7.4
argon2-cffi==23.1.0

# REEMPLAZO: Se eliminó python-jose (abandonado).
# PyJWT maneja todo lo necesario para JWT de forma segura.
pyjwt==2.8.0
cryptography>=42.0.5

# ============================================================================
# VALIDATION & SERIALIZATION
# ============================================================================
pydantic>=2.7.0          # Pydantic v2 es mucho más rápido en 3.12
pydantic-settings>=2.2.1
email-validator==2.1.1
jsonschema==4.21.1

# ============================================================================
# CSRF & FORMS (Solo si usas Flask/Jinja2)
# ============================================================================
flask-wtf==1.2.1
wtforms==3.1.2

# ============================================================================
# RATE LIMITING
# ============================================================================
slowapi==0.1.9

# ============================================================================
# BACKGROUND TASKS
# ============================================================================
apscheduler==3.10.4

# ============================================================================
# MONITORING & SYSTEM
# ============================================================================
psutil==5.9.8            # Versión estable para 3.12

# ============================================================================
# HTTP CLIENT
# ============================================================================
httpx==0.27.0            # Actualización recomendada para async

# ============================================================================
# UTILITIES
# ============================================================================
python-dotenv==1.0.1
pytz==2024.1

# ============================================================================
# SANITIZATION
# ============================================================================
bleach==6.1.0

# ============================================================================
# DEVELOPMENT & TESTING
# ============================================================================
pytest==8.1.1
pytest-asyncio==0.23.6
pytest-cov==5.0.0
black==24.3.0
flake8==7.0.0
mypy==1.9.0

# ============================================================================
# PRODUCTION SERVER
# ============================================================================
gunicorn==21.2.0

# ============================================================================
# OPTIONAL - Si necesitas características adicionales
# ============================================================================

# Redis (si decides usar cache distribuido en el futuro)
# redis==5.0.1
# aioredis==2.0.1

# Celery (si decides usar para background tasks más complejos)
# celery==5.3.4

# Excel/CSV avanzado
# openpyxl==3.1.2
# xlsxwriter==3.1.9

# PDF generation
# reportlab==4.0.9
# weasyprint==60.2

# Logging avanzado
# python-json-logger==2.0.7

# Sentry para error tracking
# sentry-sdk==1.39.2


Desglose de Dependencias Críticas
FastAPI & Flask
fastapi: API REST backend
uvicorn: Servidor ASGI para FastAPI
flask: Server-side rendering con Jinja2
Base de Datos
sqlalchemy[asyncio]: ORM con soporte async
aiomysql: Driver MySQL async
asyncmy: Driver alternativo (más rápido en algunos casos)
alembic: Migraciones de base de datos
Seguridad (Argon2)
passlib[argon2]: Framework de hashing
argon2-cffi: Backend de Argon2
python-jose[cryptography]: JWT tokens
cryptography: Encriptación adicional
Data Processing
pandas: Manipulación de datos (app-side joins)
numpy: Operaciones numéricas
Validación
pydantic: Validación de schemas
jsonschema: Validación de JSON (para widgets)
Background Tasks
apscheduler: Cron jobs (paradas, particiones)

Requirements-dev
# requirements-dev.txt
-r requirements.txt

# Testing
pytest==7.4.3
pytest-asyncio==0.23.3
pytest-cov==4.1.0
pytest-mock==3.12.0
faker==22.0.0

# Code Quality
black==23.12.1
flake8==7.0.0
isort==5.13.2
mypy==1.8.0
pylint==3.0.3

# Development Tools
ipython==8.19.0
ipdb==0.13.13
watchdog==3.0.0

# Documentation
mkdocs==1.5.3
mkdocs-material==9.5.3


Checklist de integración de UI
### Fase de Integración UI

- [ ] Crear `base.html` con configuración Tailwind
- [ ] Adaptar `login.html` a Jinja2
- [ ] Crear componentes reutilizables:
  - [ ] `sidebar.html`
  - [ ] `header.html`
  - [ ] `filters_panel.html`
  - [ ] `kpi_card.html`
- [ ] Adaptar `index.html` (dashboard principal)
- [ ] Adaptar widgets individuales
- [ ] Adaptar `reporte.html` (exportación)
- [ ] Agregar HTMX para interactividad
- [ ] Agregar Chart.js para gráficos
- [ ] Probar responsividad mobile
- [ ] Probar dark mode
- [ ] Validar accesibilidad





