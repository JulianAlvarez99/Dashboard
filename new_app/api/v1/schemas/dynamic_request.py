"""
Dynamic DashboardDataRequest model — auto-generated from active filter classes.

Adding a new filter requires ONLY:
  1. A Python class file in services/filters/types/
  2. A DB row in the ``filter`` table

No manual field declarations here.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, create_model

logger = logging.getLogger(__name__)


# ── Base class with extra='allow' so unknown fields are captured ──
class _DashboardRequestBase(BaseModel):
    """Base class that allows extra fields - critical for dynamic model."""
    model_config = ConfigDict(extra="allow")


# ── Fixed fields (not filters) — always present in every request ──
_FIXED_FIELDS: Dict[str, Any] = {
    "widget_ids":  (Optional[List[int]], Field(None)),
    "include_raw": (bool,                Field(False)),
    "tenant_id":   (Optional[int],       Field(None, description="[DEPRECATED] Ignored.")),
    "role":        (Optional[str],       Field(None, description="[DEPRECATED] Ignored.")),
    "charts":      (Optional[Dict[str, str]], Field(None)),
}

# ── pydantic_type string → Python type mapping ────────────────────
_TYPE_MAP: Dict[str, Any] = {
    "Any":           Optional[Any],
    "int":           Optional[int],
    "str":           Optional[str],
    "bool":          Optional[bool],
    "List[int]":     Optional[List[int]],
    "List[str]":     Optional[List[str]],
    "Dict[str,str]": Optional[Dict[str, str]],
}

_model_cache: Optional[type] = None


def build_dashboard_request_model() -> type:
    """
    Build ``DashboardDataRequest`` dynamically from all active filter classes.

    Lazy: called on first request so the metadata cache is guaranteed loaded.
    Result is module-level cached — invalidate with ``invalidate_model_cache()``.
    """
    global _model_cache
    if _model_cache is not None:
        return _model_cache

    try:
        from new_app.services.filters.engine import filter_engine
        filter_classes = filter_engine.get_all_classes()
    except Exception as exc:
        logger.error("[DynamicRequest] Could not load filter classes: %s", exc)
        filter_classes = []

    fields: Dict[str, Any] = dict(_FIXED_FIELDS)

    for cls in filter_classes:
        python_type = _TYPE_MAP.get(cls.pydantic_type, Optional[Any])
        default = cls.default_value if cls.default_value is not None else None
        fields[cls.param_name] = (python_type, Field(default))
        logger.debug(
            "[DynamicRequest] field=%s  type=%s  default=%r",
            cls.param_name, cls.pydantic_type, default,
        )

    # Use _DashboardRequestBase so extra='allow' captures unknown fields
    model = create_model("DashboardDataRequest", __base__=_DashboardRequestBase, **fields)
    
    # Only cache if we actually got filter classes. If none were found,
    # the metadata cache wasn't loaded yet — retry on next request.
    if filter_classes:
        _model_cache = model
        logger.info(
            "[DynamicRequest] Model built and cached — %d filter fields + %d fixed fields",
            len(filter_classes), len(_FIXED_FIELDS),
        )
    else:
        logger.warning(
            "[DynamicRequest] Model built WITHOUT filter fields (cache not loaded yet) — will retry"
        )
    
    return model


def invalidate_model_cache() -> None:
    """
    Force the next request to rebuild the Pydantic model.
    Call this after a metadata cache reload so new/removed filters
    are reflected in the request schema.
    """
    global _model_cache
    _model_cache = None
    logger.info("[DynamicRequest] Model cache invalidated — will rebuild on next request.")


def get_dashboard_request_model() -> type:
    """Lazy singleton — expose to the rest of the app."""
    return build_dashboard_request_model()
