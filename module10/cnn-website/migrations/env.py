"""Entry point for every alembic command -- the async variant."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Works because of `prepend_sys_path = .` in alembic.ini.
from news.models import Base
from news.settings import settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.database_url)

# "What the schema should be". Left as None, every migration comes out empty.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """`alembic upgrade head --sql`: print the SQL, connect to nothing."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """The sync half, handed a connection by run_sync()."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # Without these two, a changed column type or server_default is not noticed.
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """NullPool: a migration is one short-lived process, nothing to amortise."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    # Without this, asyncio complains about a pool torn down at interpreter exit.
    await connectable.dispose()


def run_migrations_online() -> None:
    """Alembic's command layer is sync, so the loop is started here."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
