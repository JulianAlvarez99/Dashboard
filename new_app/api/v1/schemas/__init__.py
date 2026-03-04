"""
API v1 Schemas — Pydantic request/response models for all endpoints.

Importing from here keeps endpoint modules thin and avoids circular imports.
"""

from new_app.api.v1.schemas.detection_schemas import (
    DetectionCountResponse,
    DetectionQueryRequest,
)
from new_app.api.v1.schemas.dashboard_schemas import (
    DashboardDataRequest,
    DashboardDataResponse,
    DashboardMetadataResponse,
)

__all__ = [
    "DetectionCountResponse",
    "DetectionQueryRequest",
    "DashboardDataRequest",
    "DashboardDataResponse",
    "DashboardMetadataResponse",
]
