import asyncio
import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.config import settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.models import audit_event as _audit_models  # noqa: F401
from app.infrastructure.database.models import meeting as _meeting_models  # noqa: F401
from app.infrastructure.database.models import recording as _recording_models  # noqa: F401
from app.infrastructure.database.models import user as _user_models  # noqa: F401

# Import model modules above so every table is registered in Base.metadata.

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Tests may provide an isolated database explicitly. Normal CLI use continues to
# resolve the URL from typed application settings.
database_url = config.attributes.get(
    "database_url", settings.db.async_database_url
)
config.set_main_option("sqlalchemy.url", database_url)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
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
