"""
Audit services package.

Exports:
  audit_service      → AuditLogService  (login/logout security events)
  query_log_service  → QueryLogService  (dashboard query activity)
"""

from new_app.services.audit.audit_service import audit_service
from new_app.services.audit.query_log_service import query_log_service

__all__ = ["audit_service", "query_log_service"]
