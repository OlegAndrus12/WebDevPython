"""Точка входу для кожної команди alembic.

Цей файл виконується наново на кожен `alembic upgrade`, `revision`, `history`
-- Alembic імпортує його, а не викликає з нього функцію. Тому весь код тут
верхнього рівня: у кінці файла одразу йде запуск міграцій.

Що тут дописано поверх згенерованого `alembic init`:
  * `target_metadata = Base.metadata`  -- без цього autogenerate завжди порожній;
  * URL береться з db.py, а не з alembic.ini -- одне джерело правди;
  * `render_as_batch=True`             -- без цього ALTER TABLE у SQLite падає.
"""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# `prepend_sys_path = .` в alembic.ini кладе теку alembic_ex у sys.path, тому
# ці два імпорти працюють -- за умови, що alembic запускають з alembic_ex.
from db import DB_URL
from models import Base

# Об'єкт Config -- це прочитаний alembic.ini плюс аргументи командного рядка
# (наприклад -x, або --sql).
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Перекриваємо порожній sqlalchemy.url з ini. Так само сюди підставляють
# os.environ["DATABASE_URL"] у проєктах, де база не лежить файлом поруч.
config.set_main_option("sqlalchemy.url", DB_URL)

# "Як має бути". autogenerate порівнює цю MetaData з тим, що реально в базі,
# і генерує різницю. `target_metadata = None` (значення за замовчуванням)
# означає порожню різницю -- міграція вийде без жодної операції.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """`alembic upgrade head --sql`: надрукувати SQL, нікуди не підключаючись.

    Потрібно там, де міграції на прод накочує DBA руками, а не застосунок.
    `literal_binds=True` -- вписати значення параметрів прямо в текст SQL,
    бо приймати `?`-плейсхолдери нема кому.
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
    """Звичайний режим: підключитися й виконати міграції.

    NullPool -- міграція це один короткий процес, тримати пул нема сенсу.
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
            # Головний рядок для SQLite. SQLite вміє з ALTER TABLE тільки
            # RENAME і ADD COLUMN -- ні DROP COLUMN зі старих версій, ні зміни
            # типу, ні додавання constraint. Batch mode обходить це так:
            # створює нову таблицю з потрібною схемою, переливає дані, видаляє
            # стару, перейменовує нову. Операції в міграції треба писати як
            # `with op.batch_alter_table("books") as batch_op`.
            render_as_batch=True,
            # За замовчуванням autogenerate не помічає зміну типу колонки
            # (String(120) -> String(200)). З цим -- помічає. У SQLite тип
            # умовний, тож іноді дає хибні спрацювання: згенеровану міграцію
            # все одно читають очима перед тим, як накотити.
            compare_type=True,
            # Те саме для server_default.
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
