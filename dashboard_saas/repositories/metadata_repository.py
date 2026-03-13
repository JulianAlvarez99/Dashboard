"""
MetadataRepository — SQL queries for reference data.

All queries are plain SQL strings executed via SQLAlchemy text().
Returns dict-indexed data ready to be stored in MetadataCache.
"""

import logging
from typing import Dict, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class MetadataRepository:
    """
    Reads reference/metadata tables from the database.

    Each method receives a SQLAlchemy Session and returns a dict
    keyed by primary ID → row dict.
    """

    # ─── Tenant DB queries ──────────────────────────────────────

    @staticmethod
    def fetch_production_lines(session: Session) -> Dict[int, dict]:
        """Active production lines."""
        result = session.execute(text(
            "SELECT line_id, line_name, line_code, is_active, "
            "availability, performance, downtime_threshold, "
            "auto_detect_downtime "
            "FROM production_line WHERE is_active = 1"
        ))
        rows = result.mappings().all()
        logger.debug("Loaded %d production lines", len(rows))
        return {row["line_id"]: dict(row) for row in rows}

    @staticmethod
    def fetch_areas(session: Session) -> Dict[int, dict]:
        """All areas."""
        result = session.execute(text(
            "SELECT area_id, line_id, area_name, area_type, area_order, "
            "coord_x1, coord_y1, coord_x2, coord_y2 FROM area"
        ))
        rows = result.mappings().all()
        logger.debug("Loaded %d areas", len(rows))
        return {row["area_id"]: dict(row) for row in rows}

    @staticmethod
    def fetch_products(session: Session) -> Dict[int, dict]:
        """All products."""
        result = session.execute(text(
            "SELECT product_id, product_name, product_code, "
            "product_weight, product_color, production_std, product_per_batch "
            "FROM product"
        ))
        rows = result.mappings().all()
        logger.debug("Loaded %d products", len(rows))
        return {row["product_id"]: dict(row) for row in rows}

    @staticmethod
    def fetch_shifts(session: Session) -> Dict[int, dict]:
        """Active shifts."""
        result = session.execute(text(
            "SELECT shift_id, shift_name, description, shift_status, "
            "days_implemented, start_time, end_time, is_overnight "
            "FROM shift WHERE shift_status = 1"
        ))
        rows = result.mappings().all()
        logger.debug("Loaded %d shifts", len(rows))
        return {row["shift_id"]: dict(row) for row in rows}

    @staticmethod
    def fetch_filters(session: Session) -> Dict[int, dict]:
        """Active filters, ordered by display_order."""
        result = session.execute(text(
            "SELECT filter_id, filter_name, description, filter_status, "
            "display_order, additional_filter "
            "FROM filter WHERE filter_status = 1 ORDER BY display_order"
        ))
        rows = result.mappings().all()
        logger.debug("Loaded %d filters", len(rows))
        return {row["filter_id"]: dict(row) for row in rows}

    @staticmethod
    def fetch_failures(session: Session) -> Dict[int, dict]:
        """All failure types."""
        result = session.execute(text(
            "SELECT failure_id, type_failure, description FROM failure"
        ))
        rows = result.mappings().all()
        logger.debug("Loaded %d failures", len(rows))
        return {row["failure_id"]: dict(row) for row in rows}

    @staticmethod
    def fetch_incidents(session: Session) -> Dict[int, dict]:
        """All incidents."""
        result = session.execute(text(
            "SELECT incident_id, failure_id, incident_code, "
            "description, has_solution, solution FROM incident"
        ))
        rows = result.mappings().all()
        logger.debug("Loaded %d incidents", len(rows))
        return {row["incident_id"]: dict(row) for row in rows}

    # ─── Global DB queries ──────────────────────────────────────

    @staticmethod
    def fetch_widget_catalog(session: Session) -> Dict[int, dict]:
        """All registered widgets from global DB."""
        result = session.execute(text(
            "SELECT widget_id, widget_name, description FROM widget_catalog"
        ))
        rows = result.mappings().all()
        logger.debug("Loaded %d widgets from catalog", len(rows))
        return {row["widget_id"]: dict(row) for row in rows}

    @staticmethod
    def fetch_dashboard_template(session: Session, tenant_id: int, role_access: str) -> Optional[dict]:
        """Fetch layout config for a given tenant and role."""
        result = session.execute(
            text(
                "SELECT layout_config FROM dashboard_template "
                "WHERE tenant_id = :tenant_id AND role_access = :role"
            ),
            {"tenant_id": tenant_id, "role": role_access}
        )
        row = result.fetchone()
        if row and row[0]:
            try:
                import json
                return json.loads(row[0]) if isinstance(row[0], str) else row[0]
            except Exception as e:
                logger.error("Error parsing layout_config: %s", e)
                return {}
        return None
