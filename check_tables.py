"""Quick check: list detection table names and production_line rows."""
from dashboard_saas.core.database import db_manager
from dashboard_saas.core.config import settings
from sqlalchemy import text

db = settings.DEFAULT_DB_NAME
engine = db_manager._get_or_create_engine(db)

with engine.connect() as conn:
    # Show detection tables
    result = conn.execute(text("SHOW TABLES LIKE 'detection%'"))
    tables = [row[0] for row in result]
    print("Detection tables:", tables)

    # Show production lines with line_code
    result = conn.execute(text("SELECT line_id, line_name, line_code FROM production_line"))
    for row in result:
        print(f"  Line {row[0]}: name={row[1]}, code={row[2]}")
