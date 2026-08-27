"""Сесія: одиниця роботи, commit/rollback і що таке expire_on_commit.

A Session is not a connection -- it is a workspace. You change objects, it works
out the INSERT/UPDATE/DELETE statements and their order, and sends them at flush.
Its life is one logical operation: one web request, one script, one task. Cheap to
create, never shared between threads.

    uv run 06_session_basics.py
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from models import Base, User
from seed import make_engine

engine = make_engine(memory=True)
Base.metadata.create_all(engine)

# One factory, made once at import time; one Session per operation.
SessionLocal = sessionmaker(engine)


# --- 1. The normal shape of every session block -------------------------------
with SessionLocal() as session:                     # closes on exit
    session.add(User(name="Олена", email="olena@example.com", age=31))
    session.commit()                                # nothing is written before this

with SessionLocal() as session:
    print("1. committed:", session.scalars(select(User)).all())

# --- 2. flush() sends the SQL, commit() ends the transaction -------------------
with SessionLocal() as session:
    user = User(name="Петро", email="petro@example.com", age=45)
    session.add(user)
    print("\n2. before flush -> id =", user.id)
    session.flush()                                 # INSERT now, still in the txn
    print("   after flush  -> id =", user.id)
    session.commit()

# --- 3. rollback() undoes everything since the last commit --------------------
with SessionLocal() as session:
    user = session.get(User, 1)                     # get() = fetch by primary key
    user.age = 99
    session.add(User(name="Ірина", email="iryna@example.com", age=22))
    session.rollback()
    print("\n3. after rollback -> age =", session.get(User, 1).age,
          "| users =", session.scalar(select(func.count(User.id))))
