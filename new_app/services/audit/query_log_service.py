"""
QueryLogService — Dashboard query activity log.

Single Responsibility: write user query activity to the ``user_query``
table (already exists in camet_global DB).

Writes are fire-and-forget: the caller should NOT await this for
request latency reasons.  Any write failure is logged and silently
swallowed — a missing query log must never break a dashboard response.

DB table: ``user_query`` (camet_global)
  query_id        int PK auto_increment
  user_id         bigint FK(user.user_id)
  username        varchar(50)
  slq_query       text          ← typo in DB column name; kept verbatim
  query_parameters text          ← JSON-serialised filter dict
  start_date      date
  start_time      time
  end_date        date
  end_time        time
  line            varchar(20)   ← line_id / "all"
  interval_type   varchar(20)
  created_at      timestamp
"""

import json
import logging
import threading
from datetime import date, datetime, time
from typing import Any, Dict, Optional

from new_app.core.database import db_manager
from new_app.models.global_models import UserQuery

logger = logging.getLogger(__name__)


class QueryLogService:
    """Writes dashboard query events to ``user_query``."""

    # ── Public API ────────────────────────────────────────────────

    def log_query_async(
        self,
        user_id: int,
        username: str,
        filters: Dict[str, Any],
        line: str,
        interval_type: str,
        sql_description: str = "dashboard_data",
        duration_ms: Optional[int] = None,
    ) -> None:
        """Fire-and-forget wrapper: launches the DB write in a daemon thread.

        Call this at the end of the dashboard endpoint handler so the
        response is returned immediately without waiting for the log write.
        """
        threading.Thread(
            target=self._write_sync,
            args=(user_id, username, filters, line, interval_type,
                  sql_description, duration_ms),
            daemon=True,
        ).start()

    # ── Private ───────────────────────────────────────────────────

    def _write_sync(
        self,
        user_id: int,
        username: str,
        filters: Dict[str, Any],
        line: str,
        interval_type: str,
        sql_description: str,
        duration_ms: Optional[int],
    ) -> None:
        """Synchronous DB write — runs inside the daemon thread."""
        try:
            daterange = filters.get("daterange") or {}
            start_dt = self._parse_date(daterange.get("start_date"))
            start_tm = self._parse_time(daterange.get("start_time"))
            end_dt = self._parse_date(daterange.get("end_date"))
            end_tm = self._parse_time(daterange.get("end_time"))

            # Embed duration_ms in query_parameters if provided
            params_dict = dict(filters)
            if duration_ms is not None:
                params_dict["_duration_ms"] = duration_ms

            with db_manager.get_global_session_sync() as db:
                record = UserQuery(
                    user_id=user_id,
                    username=username[:50],
                    slq_query=sql_description[:65535],   # text field; column typo preserved
                    query_parameters=json.dumps(params_dict, ensure_ascii=False, default=str),
                    start_date=start_dt,
                    start_time=start_tm,
                    end_date=end_dt,
                    end_time=end_tm,
                    line=str(line)[:20],
                    interval_type=str(interval_type)[:20],
                )
                db.add(record)
                db.commit()
                logger.debug(
                    "[QueryLog] Logged query for user_id=%s line=%s interval=%s",
                    user_id, line, interval_type,
                )
        except Exception as exc:
            logger.error("[QueryLog] Failed to write query log: %s", exc)

    @staticmethod
    def _parse_date(value: Any) -> date:
        """Parse a date string (YYYY-MM-DD) or return today as fallback."""
        if isinstance(value, date):
            return value
        try:
            return datetime.strptime(str(value), "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return datetime.today().date()

    @staticmethod
    def _parse_time(value: Any) -> time:
        """Parse a time string (HH:MM or HH:MM:SS) or return midnight as fallback."""
        if isinstance(value, time):
            return value
        if value is None:
            return time(0, 0, 0)
        try:
            fmt = "%H:%M:%S" if value.count(":") == 2 else "%H:%M"
            return datetime.strptime(str(value), fmt).time()
        except (ValueError, TypeError):
            return time(0, 0, 0)


# ── Singleton ─────────────────────────────────────────────────────
query_log_service = QueryLogService()
