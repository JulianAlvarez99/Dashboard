"""
Alembic env.py — Dual-database migration support.

Supports two migration namespaces:
  --db global   → camet_global (GlobalBase models)
  --db tenant   → client tenant DB (TenantBase models)

Usage:
  alembic -x db=global upgrade head
  alembic -x db=tenant upgrade head
  alembic -x db=global revision --autogenerate -m "describe change"
  alembic -x db=tenant revision --autogenerate -m "describe change"
"""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# ── Make new_app importable ──────────────────────────────────────
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ── Alembic config object ────────────────────────────────────────
config = context.config

# ── Logging ─────────────────────────────────────────────────────
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Import both model bases ──────────────────────────────────────
from new_app.core.database import GlobalBase, TenantBase  # noqa: E402
from new_app.core.config import settings  # noqa: E402

# ── Determine which DB namespace to migrate ──────────────────────
# Pass with:  alembic -x db=global upgrade head
_db_target = context.get_x_argument(as_dictionary=True).get("db", "global")

if _db_target == "global":
    target_metadata = GlobalBase.metadata
    _db_url_sync = settings.global_db_url_sync
elif _db_target == "tenant":
    target_metadata = TenantBase.metadata
    _db_url_sync = settings.tenant_db_url_sync
else:
    raise ValueError(
        f"Unknown --db target: '{_db_target}'. Use 'global' or 'tenant'."
    )


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL without a live DB connection)."""
    context.configure(
        url=_db_url_sync,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Separate version table per database so versions don't collide
        version_table=f"alembic_version_{_db_target}",
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (live DB connection)."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _db_url_sync

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table=f"alembic_version_{_db_target}",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
