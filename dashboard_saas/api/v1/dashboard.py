"""
Dashboard API — Filter options, apply filters, raw data.

Phase 3: Focus on filter options and SQL clause generation.
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from dashboard_saas.core.cache import metadata_cache
from dashboard_saas.core.database import db_manager
from dashboard_saas.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


# ── Pydantic models for request/response ─────────────────────────

class ApplyFiltersRequest(BaseModel):
    """Request body for applying filters."""
    filters: Dict[str, Any]  # { param_name: value, ... }


class ApplyFiltersResponse(BaseModel):
    """Response with the SQL query and raw data."""
    status: str
    tables_queried: List[str]
    query: str
    params: Dict[str, Any]
    row_count: int
    data: List[Dict]

# ── Apply filters → build query → execute → return raw data ─────

@router.post("/apply-filters", response_model=ApplyFiltersResponse)
async def apply_filters(request: ApplyFiltersRequest):
    """
    Endpoint principal para aplicar filtros y obtener datos crudos.

    Flujo de ejecución:
    1. Validation: Valida que los filtros obligatorios estén presentes (agnóstico).
    2. Table Resolution: Pregunta a los filtros en qué tabla/s debe buscar.
    3. Clause Collection: Recolecta las condiciones "WHERE" de cada filtro.
    4. Execution: Ejecuta la/s consulta/s contra la base de datos del cliente.
    5. Return: Devuelve los registros agrupados para ser pintados o procesados en Frontend.
    """
    from sqlalchemy import text
    from dashboard_saas.services.filters.engine import filter_engine
    from dashboard_saas.services.data.query_builder import query_builder

    filter_values = request.filters

    # 1. Validación Genérica
    # Le pasamos el diccionario de valores enviados por el usuario al motor de filtros.
    # El motor revisará automáticamente qué filtros son 'required' y si falta alguno, devuelve error.
    validation_errors = filter_engine.validate_request(filter_values)
    if validation_errors:
        raise HTTPException(
            status_code=400, 
            detail=", ".join(validation_errors)
        )

    # 2. Resolución Dinámica de Tablas
    # Algunos filtros (como el de Línea de Producción) no aportan un "WHERE", sino que definen la tabla "FROM"
    # Le preguntamos a todos los filtros si alguno tiene algo que decir sobre a qué tabla debemos buscar.
    table_names = filter_engine.get_target_tables(filter_values)
    if not table_names:
        raise HTTPException(
            status_code=400,
            detail="Faltan filtros que especifiquen qué tablas buscar (ej: Línea)."
        )

    # 3. Recolección de Cláusulas SQL (WHERE)
    # Recorremos cada filtro cargado con su valor actual y le pedimos que nos devuelva su clausula de SQL.
    # Ej: ("detected_at > :start", {"start": "2024..."})
    query_clauses, query_params = filter_engine.collect_sql_clauses(filter_values)

    # 4. Configuración del Entorno de Base de Datos
    all_rows: List[Dict] = []
    
    # 4.1 Buscamos en caché de qué cliente es la sesión actual para saber a qué BD conectarnos
    db_name = metadata_cache.current_tenant
    if not db_name:
        raise HTTPException(status_code=500, detail="No tenant loaded in cache")

    # 5. Iteración y Ejecución de Consultas
    # Si el usuario eligió un "grupo" de líneas, 'table_names' tendrá múltiples tablas.
    # El QueryBuilder armará un SELECT por cada tabla distinta y luego iremos uniendo (extend) los resultados.
    for table_name in table_names:
        # 5.1 Construimos el string de la consulta final ("SELECT ... FROM table WHERE 1=1 AND ...")
        sql = query_builder.build_detection_query(table_name, query_clauses)

        try:
            # 5.2 Obtenemos una sesión sincrónica a la base de datos del cliente
            with db_manager.get_tenant_session(db_name) as session:
                # 5.3 Ejecutamos mediante text() inyectando los parámetros para evitar SQL Injection
                result = session.execute(text(sql), query_params)
                # 5.4 Convertimos el set de resultados en una lista de diccionarios planos
                rows = [dict(row) for row in result.mappings().all()]
                all_rows.extend(rows)
                logger.info("Queried %s: %d rows", table_name, len(rows))
        except Exception as e:
            logger.error("Query failed for %s: %s", table_name, e, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

    # 6. Preparar respuesta para transparencia y depuración en Frontend
    # Generamos de nuevo el SQL de la primera tabla solo para mostrar al usuario qué fue lo que se ejecutó por debajo
    display_sql = query_builder.build_detection_query(
        table_names[0], query_clauses
    )

    return ApplyFiltersResponse(
        status="ok",
        tables_queried=table_names,
        query=display_sql,  # El string SQL crudo (ej: "SELECT ... FROM ...")
        params={k: str(v) for k, v in query_params.items()}, # Los valores formateados
        row_count=len(all_rows),
        data=all_rows,      # La lista gigante con los registros sueltos
    )
