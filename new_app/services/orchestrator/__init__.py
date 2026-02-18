"""
Orchestrator package — Dashboard Execution Workflow (Etapa 6).

Modules:
  context    — DashboardContext data container
  resolver   — Widget/layout resolution
  assembler  — Response JSON assembly
  pipeline   — DashboardOrchestrator coordinator

Usage::

    from new_app.services.orchestrator import dashboard_orchestrator

    result = await dashboard_orchestrator.execute(session, params, tid, role)
"""

from new_app.services.orchestrator.context import DashboardContext
from new_app.services.orchestrator.pipeline import (
    DashboardOrchestrator,
    dashboard_orchestrator,
)
from new_app.services.orchestrator.resolver import WidgetResolver
from new_app.services.orchestrator.assembler import ResponseAssembler

__all__ = [
    "DashboardContext",
    "DashboardOrchestrator",
    "dashboard_orchestrator",
    "WidgetResolver",
    "ResponseAssembler",
]
