"""
FastAPI dependencies — Eliminates boilerplate in detection endpoints.

Single Responsibility: provide reusable FastAPI ``Depends()`` callables
for cache validation, tenant resolution, and common request parsing.

Usage in endpoints::

    @router.post("/query")
    async def query_detections(
        ctx: TenantContext = Depends(require_tenant),
        req: DetectionQueryRequest = ...,
    ):
        # ctx.db_name is guaranteed to be set
        # no need for _check_cache() or tenant checks
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from fastapi import Depends, HTTPException

from new_app.core.cache import metadata_cache
from new_app.services.data.line_resolver import line_resolver


@dataclass
class TenantContext:
    """Validated tenant context — guaranteed non-null db_name."""
    db_name: str


def require_cache() -> None:
    """Dependency: ensure MetadataCache is loaded (user has logged in)."""
    if not metadata_cache.is_loaded:
        raise HTTPException(
            status_code=503, detail="Cache not loaded — log in first"
        )


def require_tenant(
    _: None = Depends(require_cache),
) -> TenantContext:
    """
    Dependency: ensure a tenant is loaded and return its context.

    Chains ``require_cache`` automatically, so endpoints only need
    ``Depends(require_tenant)``.
    """
    db_name = metadata_cache.current_tenant
    if not db_name:
        raise HTTPException(status_code=503, detail="No tenant loaded")
    return TenantContext(db_name=db_name)


def resolve_line_ids_from_cleaned(cleaned: Dict[str, Any]) -> List[int]:
    """
    Resolve line IDs from a cleaned filter dict.

    Raises HTTP 400 if no lines can be resolved.
    """
    line_ids = line_resolver.resolve(cleaned)
    if not line_ids:
        raise HTTPException(
            status_code=400,
            detail="No production lines found for the given parameters",
        )
    return line_ids
