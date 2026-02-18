"""
API v1 — Router aggregation.
"""

from fastapi import APIRouter

from new_app.api.v1.system import router as system_router
from new_app.api.v1.filters import router as filters_router
from new_app.api.v1.layout import router as layout_router
from new_app.api.v1.detections import router as detections_router
from new_app.api.v1.broker import router as broker_router
from new_app.api.v1.dashboard import router as dashboard_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(system_router)
api_router.include_router(filters_router)
api_router.include_router(layout_router)
api_router.include_router(detections_router)
api_router.include_router(broker_router)
api_router.include_router(dashboard_router)
