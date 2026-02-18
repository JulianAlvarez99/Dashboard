"""
APIConfig — YAML loader for external API definitions.

Single Responsibility: parse ``external_apis.yml`` into typed dataclasses.
No HTTP calls, no caching, no business logic.

Usage::

    from new_app.services.broker.api_config import api_config_loader

    configs = api_config_loader.get_all()       # dict[str, APIEndpoint]
    ep = api_config_loader.get("erp_production") # APIEndpoint | None
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

# Path to the YAML config file (relative to new_app/config/)
_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "external_apis.yml"


# ── Dataclass ────────────────────────────────────────────────────

@dataclass(frozen=True)
class APIEndpoint:
    """
    Immutable definition of a single external API source.

    Parsed from one entry in ``external_apis.yml``.
    """
    api_id: str
    name: str
    base_url: str
    method: str = "GET"
    timeout: int = 10
    auth_type: str = "none"
    auth_env_var: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    body: Dict[str, Any] = field(default_factory=dict)
    response_key: Optional[str] = None
    cache_ttl: int = 0
    enabled: bool = True


# ── Loader ───────────────────────────────────────────────────────

class APIConfigLoader:
    """
    Loads and caches the parsed external API definitions from YAML.

    The YAML is read once on first access and cached in memory.
    Call ``reload()`` to re-read after manual edits.
    """

    def __init__(self, config_path: Path = _CONFIG_PATH):
        self._config_path = config_path
        self._endpoints: Dict[str, APIEndpoint] = {}
        self._loaded = False

    def get_all(self) -> Dict[str, APIEndpoint]:
        """Return all configured API endpoints (keyed by api_id)."""
        self._ensure_loaded()
        return dict(self._endpoints)

    def get(self, api_id: str) -> Optional[APIEndpoint]:
        """Return a single endpoint by its api_id, or ``None``."""
        self._ensure_loaded()
        return self._endpoints.get(api_id)

    def get_enabled(self) -> Dict[str, APIEndpoint]:
        """Return only endpoints with ``enabled: true``."""
        self._ensure_loaded()
        return {k: v for k, v in self._endpoints.items() if v.enabled}

    def list_ids(self) -> List[str]:
        """Return all registered api_id keys."""
        self._ensure_loaded()
        return list(self._endpoints.keys())

    def reload(self) -> None:
        """Force re-read of the YAML file."""
        self._loaded = False
        self._endpoints.clear()
        self._ensure_loaded()

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    # ── Internal ─────────────────────────────────────────────

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._load()

    def _load(self) -> None:
        """Parse the YAML file into APIEndpoint dataclasses."""
        if not self._config_path.exists():
            logger.warning(
                f"[APIConfig] Config file not found: {self._config_path}"
            )
            self._loaded = True
            return

        try:
            raw = yaml.safe_load(self._config_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            logger.error(f"[APIConfig] YAML parse error: {exc}")
            self._loaded = True
            return

        if not raw or not isinstance(raw, dict):
            logger.info("[APIConfig] No APIs configured in YAML")
            self._loaded = True
            return

        for api_id, definition in raw.items():
            if not isinstance(definition, dict):
                continue
            try:
                endpoint = APIEndpoint(
                    api_id=api_id,
                    name=definition.get("name", api_id),
                    base_url=definition["base_url"],
                    method=definition.get("method", "GET").upper(),
                    timeout=int(definition.get("timeout", 10)),
                    auth_type=definition.get("auth_type", "none"),
                    auth_env_var=definition.get("auth_env_var"),
                    headers=definition.get("headers") or {},
                    params=definition.get("params") or {},
                    body=definition.get("body") or {},
                    response_key=definition.get("response_key"),
                    cache_ttl=int(definition.get("cache_ttl", 0)),
                    enabled=definition.get("enabled", True),
                )
                self._endpoints[api_id] = endpoint
            except (KeyError, ValueError, TypeError) as exc:
                logger.error(
                    f"[APIConfig] Skipping invalid entry '{api_id}': {exc}"
                )

        self._loaded = True
        logger.info(
            f"[APIConfig] Loaded {len(self._endpoints)} API endpoint(s)"
        )


# ── Singleton ────────────────────────────────────────────────────
api_config_loader = APIConfigLoader()
