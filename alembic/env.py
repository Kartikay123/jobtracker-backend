"""Alembic environment — async-aware.

The default Alembic template is sync. We replace it with the official async
recipe so we can reuse the same DATABASE_URL (asyncpg driver) the app uses.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from app.core.config import settings
from app.db.base import Base

# Import the models package so every ORM class registers on Base.metadata.
# Without this, `alembic revision --autogenerate` produces empty diffs.
import app.models  # noqa: F401


# --- Alembic config ---
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject the async DATABASE_URL from our app settings (instead of alembic.ini).
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

target_metadata = Base.metadata


# --- Migration runners ---
def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (emits raw SQL).

    Useful for generating SQL files to review before applying. Not used
    day-to-day, but Alembic requires this entrypoint.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,           # detect column-type changes
        compare_server_default=True, # detect default-value changes
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Open an async engine, hand a sync wrapper to Alembic, run, dispose."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # one-shot; don't pool for migrations
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
