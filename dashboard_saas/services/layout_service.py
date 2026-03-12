"""
LayoutService — Dashboard layout resolution from dashboard_template.
"""
import logging
from typing import Dict, Optional

from dashboard_saas.core.database import db_manager
from dashboard_saas.repositories.metadata_repository import MetadataRepository

logger = logging.getLogger(__name__)

class LayoutService:
    """
    Resolves dashboard layout configurations from the global database.
    """

    @staticmethod
    def get_layout_config(tenant_id: int, role: str) -> Optional[Dict]:
        """
        Load layout_config from DB by (tenant_id, role).
        Returns None if no template row exists.
        """
        try:
            with db_manager.get_global_session() as session:
                return MetadataRepository.fetch_dashboard_template(session, tenant_id, role)
        except Exception as e:
            logger.error("Error loading layout config for tenant %s, role %s: %s", tenant_id, role, e)
            return None

layout_service = LayoutService()
