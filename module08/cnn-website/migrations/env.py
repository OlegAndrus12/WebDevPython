"""Entry point for every alembic command -- the async variant.

Alembic imports this file fresh on each `upgrade`, `revision`, `history`, so the
code sits at module level and the run happens on the last two lines.

The async part is confined to getting a connection. `op.create_table(...)` in a
revision file is ordinary sync code and stays that way: `connection.run_sync()`
hands it a sync-style connection driven by the async one underneath. That is why
the files in versions/ are identical to module07's.
"""

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

# Overwrite the empty sqlalchemy.url from the ini file.
config.set_main_option("sqlalchemy.url", settings.database_url)

# "What the schema should be". Left as None, every migration comes out empty.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """`alembic upgrade head --sql`: print the SQL, connect to nothing.

    No driver is involved, so this path needs no async at all.
    """
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
        # Notice a changed column type (String(120) -> String(200))...
        compare_type=True,
        # ...and a changed server_default.
        compare_server_default=True,
    )

    # Postgres has transactional DDL: a migration that fails halfway rolls back
    # whole and the database stays on the previous revision.
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
