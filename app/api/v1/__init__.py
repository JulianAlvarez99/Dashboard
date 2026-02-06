"""
API v1 module
"""
from fastapi import APIRouter

from app.api.v1 import filters, widgets, system, layout, dashboard

api_router = APIRouter(prefix="/api/v1")

# Include routers
api_router.include_router(filters.router, prefix="/filters", tags=["Filters"])
api_router.include_router(widgets.router, prefix="/widgets", tags=["Widgets"])
api_router.include_router(system.router, prefix="/system", tags=["System"])
api_router.include_router(layout.router, tags=["Layout"])
api_router.include_router(dashboard.router, tags=["Dashboard"])
