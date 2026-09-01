"""Entry point for every alembic command.

Alembic imports this file fresh on each `upgrade`, `revision`, `history` -- it
does not call a function inside it. That is why the code sits at module level
and the run happens on the last two lines.

Three things are added here on top of what `alembic init` generates:

  * `target_metadata = Base.metadata`  -- without it autogenerate finds nothing
  * the URL comes from settings, not alembic.ini -- one source of truth
  * `compare_type` / `compare_server_default` -- autogenerate ignores both by
    default, so a String(120) widened to String(200) would silently never
    migrate.

Unlike ../alembic_ex (SQLite), there is no `render_as_batch` here: Postgres has
a real ALTER TABLE, so Alembic can change a column in place instead of
rebuilding the table around it.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Works because of `prepend_sys_path = .` in alembic.ini.
from cnn_website.models import Base
from cnn_website.settings import settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Overwrite the empty sqlalchemy.url from the ini file.
config.set_main_option("sqlalchemy.url", settings.database_url)

# "What the schema should be". Autogenerate diffs this against the live
# database and writes the difference. Left as None (the generated default) it
# diffs against nothing, and every migration comes out empty.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """`alembic upgrade head --sql`: print the SQL, connect to nothing.

    For shops where a DBA applies migrations by hand. `literal_binds` inlines
    parameter values into the SQL text, because there is no driver on the other
    end to bind them.
    """
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """The normal path: connect and run.

    NullPool because a migration is one short-lived process -- there is nothing
    for a connection pool to amortise.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Notice a changed column type (String(120) -> String(200)).
            compare_type=True,
            # ...and a changed server_default.
            compare_server_default=True,
        )

        # Postgres has transactional DDL: if a migration fails halfway, the
        # whole thing rolls back and the database is left on the old revision.
        # This is the main practical difference from the SQLite folder.
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
