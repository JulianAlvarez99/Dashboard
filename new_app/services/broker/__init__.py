"""
Data Broker & External APIs — Etapa 4.

Modules:
  api_config           : YAML loader + dataclass for external API definitions.
  http_client          : Async HTTP wrapper with auth, timeout, error handling.
  external_api_service : Orchestrates config lookup + HTTP calls + TTL cache.
  data_broker          : Routes widgets to internal DataFrame or external API.

Public API::

    from new_app.services.broker import data_broker, external_api_service
"""

from new_app.services.broker.data_broker import data_broker
from new_app.services.broker.external_api_service import external_api_service

__all__ = ["data_broker", "external_api_service"]
