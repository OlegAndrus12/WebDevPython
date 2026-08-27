"""Робота на core рівні: MetaData і Table -- схема як Python-об'єкти.

Core level means: no classes, no ORM, no session. Just a description of the schema
(`MetaData`) and SQL expressions built from it. Everything the ORM does above this
line, it does *through* this layer.

    MetaData -- a registry of Tables. `create_all()` / `drop_all()` live here.
    Table    -- one table, and a Python object you can index: users.c.name
    Column   -- name, type, and constraints

    uv run 03_core_tables.py
"""
from pathlib import Path

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    func,
    inspect,
)
from sqlalchemy.schema import CreateTable

DB = Path(__file__).parent / "core_schema.db"
DB.unlink(missing_ok=True)
engine = create_engine(f"sqlite:///{DB}")

metadata = MetaData()

users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True),          # implies autoincrement
    Column("name", String(120), nullable=False),
    Column("email", String(120), nullable=False, unique=True),
    Column("age", Integer, nullable=False),
    # server_default is rendered into the DDL: the *database* fills it in.
    # (`default=` is the other one -- it runs in Python, at INSERT time.)
    Column("created_at", DateTime, server_default=func.now()),
    CheckConstraint("age > 10 AND age < 90", name="ck_users_age"),
)

videos = Table(
    "videos",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("title", String(200), nullable=False),
    Column("views", Integer, nullable=False, default=0),
    # A ForeignKey is what makes this a *relational* database rather than
    # two spreadsheets. ondelete is enforced by the DB, not by Python.
    Column("author_id", ForeignKey("users.id", ondelete="CASCADE"), index=True),
)

# --- 1. The DDL SQLAlchemy will send ------------------------------------------
print("--- CREATE TABLE users (as this dialect renders it) ---")
print(CreateTable(users).compile(engine))

# --- 2. create_all: emits CREATE TABLE for everything not already there -------
metadata.create_all(engine)
print("tables now in the database:", inspect(engine).get_table_names())

# create_all is idempotent -- it checks first. That is also its whole limitation:
# it creates what is missing and *never* alters what exists. Changed a column?
# create_all will not notice. That is what alembic-demo/ is for.
metadata.create_all(engine)
print("second create_all: no error, and no changes either")


engine.dispose() # manually close the connection
