# AGENTS.MD - FASE 5: Cálculo de Métricas (KPIs)

## 🎯 OBJETIVO DE LA FASE 5

Implementar el sistema completo de cálculo de métricas de producción (OEE, eficiencia, disponibilidad, calidad) con agregaciones temporales configurables y soporte para turnos complejos.

**Duración Estimada:** 1-2 semanas  
**Prioridad:** Alta (bloquea visualización de widgets)

**Dependencias:**
- ✅ FASE 1: Autenticación y base de datos
- ✅ FASE 2: Sistema de caché
- ✅ FASE 3: Motor de consultas
- ✅ FASE 4: Cálculo de paradas

---

## 📦 TASK 5.1: Service de Cálculo de OEE

### Descripción
Implementar el servicio que calcula el OEE (Overall Equipment Effectiveness) y sus componentes: Disponibilidad, Rendimiento y Calidad.

### Criterios de Aceptación
- [X] Cálculo correcto de OEE = Disponibilidad × Rendimiento × Calidad
- [X] Manejo de turnos (simples y overnight)
- [X] Exclusión de tiempo no planificado
- [X] Resultados redondeados a 2 decimales
- [X] Tests unitarios con casos edge

### Archivo: `app/services/metrics_service.py`


"""
Metrics calculation service - KPIs and production metrics
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta, time as time_type
from typing import Dict, List, Optional
import pandas as pd

from app.models.client_db import ProductionLine, Area, Shift
from app.services.detection_service import DetectionService
from app.services.downtime_service import DowntimeService
from app.core.cache import MetadataCache


class MetricsService:
    """Service for calculating production metrics and KPIs"""
    
    def __init__(self, cache: MetadataCache, db: AsyncSession):
        self.cache = cache
        self.db = db
        self.detection_service = DetectionService(cache, db)
        self.downtime_service = DowntimeService(cache, db)
    
    async def calculate_oee(
        self,
        line_id: int,
        start_date: datetime,
        end_date: datetime,
        shift_id: Optional[int] = None
    ) -> Dict:
        """
        Calculate OEE and its components
        
        OEE = Availability × Performance × Quality
        
        Args:
            line_id: Production line ID
            start_date: Start datetime
            end_date: End datetime
            shift_id: Optional shift filter
            
        Returns:
            Dictionary with OEE metrics
        """
        # Get line configuration
        line = self.cache.get_line(line_id)
        if not line:
            raise ValueError(f"Line {line_id} not found in cache")
        
        # Calculate planned production time
        planned_time = await self.calculate_planned_time(
            line_id=line_id,
            start_date=start_date,
            end_date=end_date,
            shift_id=shift_id
        )
        
        if planned_time == 0:
            return self._zero_oee_response("No planned production time in selected range")
        
        # Get downtime events
        downtimes = await self.downtime_service.get_downtimes(
            line_id=line_id,
            start_date=start_date,
            end_date=end_date
        )
        
        # Calculate total downtime in seconds
        total_downtime = sum(dt['duration'] for dt in downtimes)
        
        # Operating Time = Planned Time - Downtime
        operating_time = max(0, planned_time - total_downtime)
        
        # AVAILABILITY = (Operating Time / Planned Time) × 100
        availability = (operating_time / planned_time * 100) if planned_time > 0 else 0
        
        # Get production counts
        production_data = await self._get_production_counts(
            line_id=line_id,
            start_date=start_date,
            end_date=end_date,
            shift_id=shift_id
        )
        
        actual_production = production_data['total_output']
        
        # Target production = Standard rate × Operating time (in hours)
        operating_hours = operating_time / 3600
        target_production = line['performance'] * operating_hours
        
        # PERFORMANCE = (Actual Production / Target Production) × 100
        performance = (actual_production / target_production * 100) if target_production > 0 else 0
        # Cap performance at 100% (can't exceed target in this model)
        performance = min(performance, 100)
        
        # QUALITY = (Good Units / Total Input) × 100
        total_input = production_data['total_input']
        good_units = production_data['total_output']
        quality = (good_units / total_input * 100) if total_input > 0 else 100
        
        # Calculate rejected units
        rejected_units = max(0, total_input - good_units)
        
        # OEE = Availability × Performance × Quality / 10000
        oee = (availability * performance * quality) / 10000
        
        return {
            'oee': round(oee, 2),
            'availability': round(availability, 2),
            'performance': round(performance, 2),
            'quality': round(quality, 2),
            'metrics': {
                'planned_time_seconds': planned_time,
                'operating_time_seconds': operating_time,
                'total_downtime_seconds': total_downtime,
                'downtime_count': len(downtimes),
                'actual_production': actual_production,
                'target_production': round(target_production, 0),
                'good_units': good_units,
                'rejected_units': rejected_units,
                'total_input': total_input
            },
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
                'shift_id': shift_id
            }
        }
    
    async def calculate_planned_time(
        self,
        line_id: int,
        start_date: datetime,
        end_date: datetime,
        shift_id: Optional[int] = None
    ) -> float:
        """
        Calculate planned production time in seconds based on configured shifts
        
        Args:
            line_id: Production line ID
            start_date: Start datetime
            end_date: End datetime
            shift_id: Optional specific shift filter
            
        Returns:
            Total planned seconds
        """
        # Get active shifts for the line
        shifts = await self._get_line_shifts(line_id, shift_id)
        
        if not shifts:
            # No shifts configured - assume 24/7 operation
            return (end_date - start_date).total_seconds()
        
        total_seconds = 0.0
        current_date = start_date.date()
        end_date_only = end_date.date()
        
        while current_date <= end_date_only:
            day_name = current_date.strftime('%A')
            
            for shift in shifts:
                # Check if shift applies to this day
                if day_name not in shift['days_implemented']:
                    continue
                
                # Calculate shift start and end times for this date
                shift_start = datetime.combine(current_date, shift['start_time'])
                shift_end = datetime.combine(current_date, shift['end_time'])
                
                # Handle overnight shifts
                if shift['is_overnight']:
                    shift_end += timedelta(days=1)
                
                # Calculate intersection with requested range
                effective_start = max(shift_start, start_date)
                effective_end = min(shift_end, end_date)
                
                # Add duration if there's overlap
                if effective_end > effective_start:
                    duration = (effective_end - effective_start).total_seconds()
                    total_seconds += duration
            
            current_date += timedelta(days=1)
        
        return total_seconds
    
    async def _get_line_shifts(
        self,
        line_id: int,
        shift_id: Optional[int] = None
    ) -> List[Dict]:
        """Get active shifts from cache"""
        all_shifts = self.cache.get_all_shifts()
        
        if shift_id:
            # Filter by specific shift
            shift = self.cache.get_shift(shift_id)
            return [shift] if shift else []
        
        # Return all active shifts
        return [s for s in all_shifts.values() if s.get('shift_status', True)]
    
    async def _get_production_counts(
        self,
        line_id: int,
        start_date: datetime,
        end_date: datetime,
        shift_id: Optional[int] = None
    ) -> Dict:
        """
        Get production counts from input and output areas
        """
        # Get input and output areas
        input_area = await self._get_area_by_type(line_id, 'input')
        output_area = await self._get_area_by_type(line_id, 'output')
        
        if not input_area or not output_area:
            return {
                'total_input': 0,
                'total_output': 0
            }
        
        # Count detections in input area
        input_count = await self.detection_service.count_detections(
            line_id=line_id,
            area_id=input_area['area_id'],
            start_date=start_date,
            end_date=end_date,
            shift_id=shift_id
        )
        
        # Count detections in output area
        output_count = await self.detection_service.count_detections(
            line_id=line_id,
            area_id=output_area['area_id'],
            start_date=start_date,
            end_date=end_date,
            shift_id=shift_id
        )
        
        return {
            'total_input': input_count,
            'total_output': output_count
        }
    
    async def _get_area_by_type(self, line_id: int, area_type: str) -> Optional[Dict]:
        """Get area by type (input, output, process)"""
        all_areas = self.cache.get_all_areas()
        
        for area in all_areas.values():
            if area['line_id'] == line_id and area['area_type'] == area_type:
                return area
        
        return None
    
    def _zero_oee_response(self, reason: str) -> Dict:
        """Return zero OEE response with reason"""
        return {
            'oee': 0.0,
            'availability': 0.0,
            'performance': 0.0,
            'quality': 0.0,
            'metrics': {
                'planned_time_seconds': 0,
                'operating_time_seconds': 0,
                'total_downtime_seconds': 0,
                'downtime_count': 0,
                'actual_production': 0,
                'target_production': 0,
                'good_units': 0,
                'rejected_units': 0,
                'total_input': 0
            },
            'reason': reason
        }


### Verificación


# Tests unitarios
pytest tests/test_metrics_oee.py -v

# Test manual
python -c "
import asyncio
from app.services.metrics_service import MetricsService
from datetime import datetime, timedelta

async def test():
    # Setup (asume DB y cache inicializados)
    metrics = MetricsService(cache, db)
    
    result = await metrics.calculate_oee(
        line_id=1,
        start_date=datetime(2024, 1, 20, 0, 0),
        end_date=datetime(2024, 1, 20, 23, 59)
    )
    
    print(f'OEE: {result[\"oee\"]}%')
    print(f'Availability: {result[\"availability\"]}%')
    print(f'Performance: {result[\"performance\"]}%')
    print(f'Quality: {result[\"quality\"]}%')

asyncio.run(test())
"


---

## 📦 TASK 5.2: Agregaciones Temporales

### Descripción
Implementar sistema de agregación de detecciones por intervalos de tiempo configurables (1min, 15min, 1hora, 1día, 1semana, 1mes).

### Criterios de Aceptación
- [X] Soporte para todos los intervalos configurados
- [X] Agregaciones eficientes con Pandas
- [X] Manejo correcto de zonas horarias
- [X] Enriquecimiento con metadatos del cache

### Archivo: `app/services/metrics_service.py` (continuación)


    async def aggregate_by_interval(
        self,
        df: pd.DataFrame,
        interval: str,
        include_weight: bool = False
    ) -> pd.DataFrame:
        """
        Aggregate detections by time interval
        
        Args:
            df: DataFrame with detection data (must have 'detected_at' column)
            interval: Interval type ('1min', '15min', '1hour', '1day', '1week', '1month')
            include_weight: Calculate total weight if True
            
        Returns:
            Aggregated DataFrame with counts and optional weights
        """
        if df.empty:
            return pd.DataFrame()
        
        # Ensure detected_at is datetime
        df['detected_at'] = pd.to_datetime(df['detected_at'])
        
        # Interval mapping
        interval_map = {
            '1min': '1T',
            '15min': '15T',
            '1hour': '1H',
            '1day': '1D',
            '1week': '1W',
            '1month': '1M'
        }
        
        resample_interval = interval_map.get(interval, '15T')
        
        # Prepare aggregation dictionary
        agg_dict = {
            'detection_id': 'count'
        }
        
        if 'product_id' in df.columns:
            agg_dict['product_id'] = lambda x: x.mode()[0] if len(x) > 0 else None
        
        if 'area_id' in df.columns:
            agg_dict['area_id'] = lambda x: x.mode()[0] if len(x) > 0 else None
        
        # Aggregate by time interval
        aggregated = df.set_index('detected_at').resample(resample_interval).agg(agg_dict)
        aggregated = aggregated.rename(columns={'detection_id': 'count'})
        
        # Calculate total weight if requested
        if include_weight and 'product_weight' in df.columns:
            # Need to merge product weights
            weight_series = df.set_index('detected_at')['product_weight'].resample(resample_interval).sum()
            aggregated['total_weight'] = weight_series
        
        # Enrich with metadata if IDs are present
        if 'product_id' in aggregated.columns and 'product_name' not in df.columns:
            aggregated['product_name'] = aggregated['product_id'].map(
                lambda x: self.cache.get_product(int(x))['product_name'] if pd.notna(x) else None
            )
        elif 'product_name' in df.columns:
            # Already enriched, just aggregate
            product_names = df.groupby('product_id')['product_name'].first()
            aggregated['product_name'] = aggregated['product_id'].map(product_names)
        
        if 'area_id' in aggregated.columns and 'area_name' not in df.columns:
            aggregated['area_name'] = aggregated['area_id'].map(
                lambda x: self.cache.get_area(int(x))['area_name'] if pd.notna(x) else None
            )
        elif 'area_name' in df.columns:
            area_names = df.groupby('area_id')['area_name'].first()
            aggregated['area_name'] = aggregated['area_id'].map(area_names)
        
        # Reset index to make detected_at a column
        aggregated = aggregated.reset_index()
        
        # Fill NaN counts with 0
        aggregated['count'] = aggregated['count'].fillna(0).astype(int)
        
        return aggregated
    
    async def calculate_total_weight(
        self,
        df: pd.DataFrame
    ) -> float:
        """
        Calculate total weight from detections DataFrame
        
        Args:
            df: DataFrame with detection data and product_id
            
        Returns:
            Total weight in kg
        """
        if df.empty or 'product_id' not in df.columns:
            return 0.0
        
        # Enrich with product weights if not present
        if 'product_weight' not in df.columns:
            df['product_weight'] = df['product_id'].map(
                lambda x: self.cache.get_product(x).get('product_weight', 0)
            )
        
        return float(df['product_weight'].sum())


### Archivo: `tests/test_metrics_aggregation.py`


"""
Unit tests for metrics aggregation
"""
import pytest
import pandas as pd
from datetime import datetime, timedelta
from app.services.metrics_service import MetricsService


@pytest.fixture
def sample_detections():
    """Create sample detection data"""
    start = datetime(2024, 1, 20, 8, 0)
    
    data = []
    for i in range(100):
        data.append({
            'detection_id': i + 1,
            'detected_at': start + timedelta(minutes=i),
            'area_id': 1,
            'product_id': 1 if i % 2 == 0 else 2
        })
    
    return pd.DataFrame(data)


@pytest.mark.asyncio
async def test_aggregate_by_1min(metrics_service, sample_detections):
    """Test 1-minute aggregation"""
    result = await metrics_service.aggregate_by_interval(
        df=sample_detections,
        interval='1min'
    )
    
    assert not result.empty
    assert 'count' in result.columns
    assert len(result) == 100  # One entry per minute


@pytest.mark.asyncio
async def test_aggregate_by_15min(metrics_service, sample_detections):
    """Test 15-minute aggregation"""
    result = await metrics_service.aggregate_by_interval(
        df=sample_detections,
        interval='15min'
    )
    
    assert not result.empty
    expected_buckets = 100 // 15 + 1
    assert len(result) >= expected_buckets


@pytest.mark.asyncio
async def test_aggregate_with_weight(metrics_service, sample_detections):
    """Test aggregation with weight calculation"""
    # Add product weights to DataFrame
    sample_detections['product_weight'] = sample_detections['product_id'].map({
        1: 5.5,
        2: 3.2
    })
    
    result = await metrics_service.aggregate_by_interval(
        df=sample_detections,
        interval='1hour',
        include_weight=True
    )
    
    assert 'total_weight' in result.columns
    assert result['total_weight'].sum() > 0


@pytest.mark.asyncio
async def test_calculate_total_weight(metrics_service, sample_detections):
    """Test total weight calculation"""
    sample_detections['product_weight'] = sample_detections['product_id'].map({
        1: 5.5,
        2: 3.2
    })
    
    total = await metrics_service.calculate_total_weight(sample_detections)
    
    # 50 products at 5.5kg + 50 products at 3.2kg
    expected = (50 * 5.5) + (50 * 3.2)
    assert total == expected


---

## 📦 TASK 5.3: Endpoint de Métricas

### Descripción
Crear endpoints FastAPI para obtener métricas OEE y resúmenes de producción.

### Archivo: `app/api/v1/metrics.py`


"""
Metrics endpoints - OEE and production metrics
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime

from app.core.database import get_client_db
from app.core.dependencies import get_current_user
from app.models.global_db import User
from app.schemas.query import QueryFilters
from app.services.metrics_service import MetricsService
from app.services.detection_service import DetectionService
from app.services.audit_service import AuditService
from app.core.cache import get_tenant_cache


router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.post("/oee", status_code=status.HTTP_200_OK)
async def calculate_oee(
    filters: QueryFilters,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(lambda: get_client_db(current_user.tenant_id))
):
    """
    Calculate OEE metrics for a production line
    
    - **line_id**: Production line ID
    - **start_date**: Start datetime
    - **end_date**: End datetime
    - **shift_id**: Optional shift filter
    
    Returns complete OEE breakdown with availability, performance, and quality
    """
    cache = get_tenant_cache(current_user.tenant_id)
    metrics_service = MetricsService(cache, db)
    audit_service = AuditService(db)
    
    try:
        # Calculate OEE
        result = await metrics_service.calculate_oee(
            line_id=filters.line_id,
            start_date=filters.start_date,
            end_date=filters.end_date,
            shift_id=filters.shift_id
        )
        
        # Audit log
        await audit_service.log_query(
            user_id=current_user.user_id,
            username=current_user.username,
            query_params={
                'type': 'oee_calculation',
                'line_id': filters.line_id,
                'start_date': filters.start_date.isoformat(),
                'end_date': filters.end_date.isoformat()
            }
        )
        
        return result
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating OEE: {str(e)}"
        )


@router.post("/summary", status_code=status.HTTP_200_OK)
async def get_production_summary(
    filters: QueryFilters,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(lambda: get_client_db(current_user.tenant_id))
):
    """
    Get comprehensive production summary
    
    Returns:
    - Total production count
    - Total weight
    - Product distribution
    - Downtime statistics
    - OEE metrics
    """
    cache = get_tenant_cache(current_user.tenant_id)
    metrics_service = MetricsService(cache, db)
    detection_service = DetectionService(cache, db)
    
    try:
        # Get detections
        df = await detection_service.get_enriched_detections(filters)
        
        # Calculate metrics
        total_production = len(df)
        total_weight = await metrics_service.calculate_total_weight(df)
        
        # Product distribution
        product_distribution = {}
        if not df.empty and 'product_name' in df.columns:
            product_distribution = df['product_name'].value_counts().to_dict()
        
        # Get OEE
        oee_result = await metrics_service.calculate_oee(
            line_id=filters.line_id,
            start_date=filters.start_date,
            end_date=filters.end_date,
            shift_id=filters.shift_id
        )
        
        return {
            'production': {
                'total_count': total_production,
                'total_weight_kg': round(total_weight, 2),
                'product_distribution': product_distribution
            },
            'oee': {
                'oee': oee_result['oee'],
                'availability': oee_result['availability'],
                'performance': oee_result['performance'],
                'quality': oee_result['quality']
            },
            'downtime': {
                'count': oee_result['metrics']['downtime_count'],
                'total_seconds': oee_result['metrics']['total_downtime_seconds']
            },
            'period': oee_result['period']
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating summary: {str(e)}"
        )


@router.post("/timeseries", status_code=status.HTTP_200_OK)
async def get_production_timeseries(
    filters: QueryFilters,
    interval: str = "15min",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(lambda: get_client_db(current_user.tenant_id))
):
    """
    Get production time series aggregated by interval
    
    - **interval**: '1min', '15min', '1hour', '1day', '1week', '1month'
    
    Returns time series data ready for Chart.js
    """
    cache = get_tenant_cache(current_user.tenant_id)
    metrics_service = MetricsService(cache, db)
    detection_service = DetectionService(cache, db)
    
    try:
        # Get detections
        df = await detection_service.get_enriched_detections(filters)
        
        if df.empty:
            return {
                'labels': [],
                'datasets': []
            }
        
        # Aggregate by interval
        aggregated = await metrics_service.aggregate_by_interval(
            df=df,
            interval=interval,
            include_weight=True
        )
        
        # Format for Chart.js
        return {
            'labels': aggregated['detected_at'].dt.strftime('%Y-%m-%d %H:%M').tolist(),
            'datasets': [{
                'label': 'Production Count',
                'data': aggregated['count'].tolist(),
                'type': 'line'
            }]
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating timeseries: {str(e)}"
        )


### Actualizar `app/api/v1/__init__.py`


from fastapi import APIRouter
from app.api.v1 import auth, metrics  # Agregar metrics

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(metrics.router, prefix="/metrics", tags=["metrics"])


---

## ✅ CHECKLIST FINAL - FASE 5

### Implementación
- [X] MetricsService con cálculo de OEE implementado
- [X] Cálculo de tiempo planificado con soporte de turnos
- [X] Manejo de turnos overnight
- [X] Agregaciones temporales con Pandas
- [X] Cálculo de peso total
- [X] Enriquecimiento con cache en agregaciones

### Endpoints
- [X] POST /api/v1/metrics/oee
- [X] POST /api/v1/metrics/summary
- [X] POST /api/v1/metrics/timeseries

### Tests
- [X] Tests unitarios de OEE
- [X] Tests de agregaciones temporales
- [X] Tests de manejo de turnos
- [X] Tests con datos vacíos
- [X] Tests de performance (< 1s)

### Verificación
- [X] Métricas calculadas correctamente
- [X] OEE validado manualmente
- [X] Agregaciones eficientes
- [X] Documentación API actualizada

---

## 🎯 ENTREGABLES FASE 5

1. **MetricsService completo** con OEE y agregaciones
2. **Endpoints REST funcionales** para métricas
3. **Tests unitarios** con coverage > 85%
4. **Documentación** de fórmulas y algoritmos
5. **Validación manual** de cálculos con datos reales