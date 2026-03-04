"""
Request helpers — shared utilities for converting Pydantic request
models into the flat ``user_params`` / ``cleaned`` dict that
FilterEngine expects.

Centralises the mapping logic that was previously duplicated in:
  - api/v1/dashboard.py  (_extract_user_params)
  - api/v1/detections.py (_build_cleaned)

Post-refactor: ``build_filter_dict`` is fully generic — it discovers
all active filter param_names from FilterEngine. Adding a new filter
does NOT require editing this file.
"""

from typing import Any, Dict

# Fields on the request model that are NOT filter params.
_CONTROL_FIELDS = {"widget_ids", "include_raw", "tenant_id", "role", "charts"}


def build_filter_dict(req) -> Dict[str, Any]:
    """
    Extract filter params from a Pydantic request model into a flat
    dict matching FilterEngine's expected ``user_params`` shape.

    Fully generic: discovers active param_names from FilterEngine so
    adding a new filter never requires touching this file.

    Args:
        req: Any Pydantic request model whose fields may include filter params.

    Returns:
        Dict of {param_name: value} for non-None filter values only.
    """
    try:
        from new_app.services.filters.engine import filter_engine
        known_params = {cls.param_name for cls in filter_engine.get_all_classes()}
    except Exception:
        # Fallback: include everything that isn't a control field
        known_params = None

    raw = req.model_dump()
    
    # DEBUG: trace line_id
    print(f"[build_filter_dict] raw.keys={list(raw.keys())}")
    print(f"[build_filter_dict] raw['line_id']={raw.get('line_id')!r}")
    print(f"[build_filter_dict] known_params={known_params}")

    if known_params is not None:
        result = {k: v for k, v in raw.items() if k in known_params and v is not None}
    else:
        result = {k: v for k, v in raw.items() if k not in _CONTROL_FIELDS and v is not None}
    
    print(f"[build_filter_dict] result={result}")
    return result
