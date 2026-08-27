"""Сесія: одиниця роботи, commit/rollback і що таке expire_on_commit.

A Session is not a connection -- it is a workspace. You change objects, it works
out the INSERT/UPDATE/DELETE statements and their order, and sends them at flush.
Its life is one logical operation: one web request, one script, one task. Cheap to
create, never shared between threads.

    uv run 05_session_basics.py
"""
from sqlalchemy import String, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.orm.exc import DetachedInstanceError

from models import Base, User
from db import make_engine

class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(120), unique=True)
    age: Mapped[int]

    def __repr__(self) -> str:
        return f"<User #{self.id} {self.name} ({self.age})>"


# "sqlite://" is an in-memory database. SQLAlchemy keeps one connection per thread
# for it, so every Session below is looking at the same data.
engine = create_engine("sqlite://")
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

# --- 4. expire_on_commit=True (the default): commit marks every object stale ---
# The next attribute read emits a fresh SELECT, so you never see a value the
# transaction has moved past. Outside the session there is nothing to select
# *with*, which is where the famous DetachedInstanceError comes from.
with SessionLocal() as session:
    olena = session.scalars(select(User).where(User.name == "Олена")).one()
    session.commit()

try:
    olena.name
except DetachedInstanceError:
    print("\n4. expire_on_commit=True  -> DetachedInstanceError after close()")

# --- 5. expire_on_commit=False: the object keeps its loaded values -------------
# Useful when the caller needs the object after the session ends (a web handler
# serialising a response). The trade-off: those values are now a snapshot.
NoExpire = sessionmaker(engine, expire_on_commit=False)
with NoExpire() as session:
    petro = session.scalars(select(User).where(User.name == "Петро")).one()
    session.commit()

print("5. expire_on_commit=False -> still readable after close():", petro)

engine.dispose()
