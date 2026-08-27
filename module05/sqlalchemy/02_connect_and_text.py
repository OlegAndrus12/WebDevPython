"""Транзакції на Core рівні: connect() vs begin(), і text() для сирого SQL.

    with engine.connect() as conn:   -> BEGIN ... ROLLBACK unless you conn.commit()
    with engine.begin()   as conn:   -> BEGIN ... COMMIT   (ROLLBACK on exception)

"Commit as you go" (`connect`) or "begin once" (`begin`). There is no third mode,
and there is no autocommit.

    uv run 02_connect_and_text.py
"""
from pathlib import Path

from sqlalchemy import create_engine, text

DB = Path(__file__).parent / "core_demo.db"
DB.unlink(missing_ok=True)
engine = create_engine(f"sqlite:///{DB}")

with engine.begin() as conn:
    conn.execute(text("CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT)"))


def count() -> int:
    with engine.connect() as conn:
        return conn.execute(text("SELECT COUNT(*) FROM notes")).scalar_one()


# --- 1. connect() without commit: the write is thrown away --------------------
with engine.connect() as conn:
    conn.execute(text("INSERT INTO notes (body) VALUES (:body)"), {"body": "lost"})
print("1. inserted inside connect(), no commit -> rows:", count())

# --- 2. connect() + explicit commit: "commit as you go" -----------------------
with engine.connect() as conn:
    conn.execute(text("INSERT INTO notes (body) VALUES (:body)"), {"body": "kept"})
    conn.commit()
print("2. same, with conn.commit()            -> rows:", count())

# --- 3. begin(): the block *is* the transaction -------------------------------
with engine.begin() as conn:
    conn.execute(text("INSERT INTO notes (body) VALUES (:body)"), {"body": "also kept"})
print("3. engine.begin() block                -> rows:", count())

# --- 4. An exception inside begin() rolls the whole block back ----------------
try:
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO notes (body) VALUES (:b)"), {"b": "half"})
        raise RuntimeError("payment provider timed out")
except RuntimeError as err:
    print(f"4. begin() + raise ({err}) -> rows:", count())

# --- 5. executemany: a list of dicts, one statement ---------------------------
with engine.begin() as conn:
    conn.execute(
        text("INSERT INTO notes (body) VALUES (:body)"),
        [{"body": f"bulk {i}"} for i in range(5)],
    )
print("5. list of param dicts = executemany   -> rows:", count())

# --- 6. Reading results: Row is a named tuple ---------------------------------
with engine.connect() as conn:
    result = conn.execute(text("SELECT id, body FROM notes ORDER BY id LIMIT 3"))
    for row in result:
        # Positional, by attribute, or as a dict -- all three work on one Row.
        print(f"6. row {row[0]} | {row.body} | {row._mapping}")

with engine.connect() as conn:
    # .scalars() takes column 0 of every row; .all() materialises the list.
    bodies = conn.execute(text("SELECT body FROM notes ORDER BY id")).scalars().all()
    print("7. scalars().all():", bodies)

engine.dispose()
