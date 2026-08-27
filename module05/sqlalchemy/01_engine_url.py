"""
`create_engine()` connects to nothing. It parses a URL, picks a dialect and a
driver, and hands you a lazy factory with a connection pool behind it. The first
real socket is opened by the first `.connect()`.

Two things to take away:
  * the URL is `dialect+driver://user:pass@host:port/dbname` -- swap the driver
    and every other file in this module keeps working unchanged;
  * an Engine is a long-lived, module-level object. One per database per process.
    Creating one per request is the classic performance bug.
"""
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

DB = Path(__file__).parent / "engine_demo.db"

# --- 1. The URL, read out loud ------------------------------------------------
for raw in [
    "sqlite:///relative.db",                     # 3 slashes: relative file path
    "sqlite:////absolute/path.db",               # 4 slashes: absolute path
    "sqlite+aiosqlite:///async.db",              # same DB, async driver
    "sqlite://",                                 # no path at all: in-memory
    "postgresql+psycopg://demo:demo@localhost:5434/module05",
    "postgresql+asyncpg://demo:demo@localhost:5434/module05",
]:
    url = make_url(raw)
    print(f"{raw:<56} dialect={url.get_backend_name():<10} driver={url.get_driver_name()}")

# --- 2. Nothing is connected yet ----------------------------------------------
DB.unlink(missing_ok=True)
engine = create_engine(f"sqlite:///{DB}")
print("\nengine created:", engine)
print("file exists on disk?", DB.exists())  # False -- no connection has been made

# --- 3. The first connect is what actually opens the database -----------------
with engine.connect() as conn:
    version = conn.execute(text("SELECT sqlite_version()")).scalar_one()
    print("first connect -> sqlite", version, "| file exists now?", DB.exists())

# --- 5. echo=True prints every statement SQLAlchemy emits ---------------------
# Turn this on whenever you are surprised by what the ORM did. It is the single
# most useful debugging switch in the library.
loud = create_engine(f"sqlite:///{DB}", echo=True)
with loud.connect() as conn:
    conn.execute(text("SELECT 1"))
