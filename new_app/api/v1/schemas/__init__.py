"""
API v1 Schemas — Pydantic request/response models for all endpoints.

Importing from here keeps endpoint modules thin and avoids circular imports.

Note: DashboardDataRequest is now built dynamically from active filter classes
via dynamic_request.py. Adding a new filter only requires a DB row + class file.
"""

from new_app.api.v1.schemas.detection_schemas import (
    DetectionCountResponse,
    DetectionQueryRequest,
)
from new_app.api.v1.schemas.dashboard_schemas import (
    DashboardDataResponse,
    DashboardMetadataResponse,
)

# DashboardDataRequest is built dynamically at runtime.
# Import the factory so callers can call get_dashboard_request_model() directly,
# or use the lazy alias below (resolved when first accessed).
from new_app.api.v1.schemas.dynamic_request import get_dashboard_request_model, invalidate_model_cache

# Lazy alias — compatible with existing `from schemas import DashboardDataRequest`.
# The model is built on first access after the metadata cache is loaded.
def __getattr__(name):
    if name == "DashboardDataRequest":
        return get_dashboard_request_model()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "DetectionCountResponse",
    "DetectionQueryRequest",
    "DashboardDataResponse",
    "DashboardMetadataResponse",
    "DashboardDataRequest",       # resolved dynamically
    "get_dashboard_request_model",
    "invalidate_model_cache",
]
