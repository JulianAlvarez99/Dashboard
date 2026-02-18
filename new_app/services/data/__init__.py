"""
Data extraction, enrichment & downtime pipeline — Etapa 3.

Modules:
  table_resolver       : Dynamic table name resolution from cache.
  line_resolver        : Line ID resolution from filter parameters.
  partition_manager    : Monthly RANGE partition management for MySQL.
  sql_clauses          : Pure functions for SQL WHERE clause construction.
  query_builder        : Dynamic SQL construction from filter params.
  detection_repository : Raw query execution with cursor-based pagination.
  downtime_repository  : Downtime events fetch with cursor pagination.
  downtime_calculator  : Gap-based downtime detection + overlap removal.
  downtime_service     : Downtime pipeline orchestrator (DB + gap + merge).
  enrichment           : Application-side joins (DataFrame → enriched DataFrame).
  export               : DataFrame serialization (CSV, XLSX).
  detection_service    : Thin orchestrator tying everything together.
"""
