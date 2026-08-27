"""select() and results: scalars() vs execute(), and why a Row is not an object.

One entry point for everything: `session.execute(statement)`. The statement can be
select(), insert(), update(), delete() or text().

The one trap: execute(select(User)) gives you **Rows**, not Users. A Row is a tuple
of whatever you selected -- `(User,)` here. scalars() unwraps column 0.

Each section gets its own `with get_session()`.

    uv run 08_select_and_results.py
"""
from sqlalchemy import func, select
from sqlalchemy.exc import MultipleResultsFound, NoResultFound

from db import drop_db, get_session
from models import User, Video


def top_videos(limit: int, min_views: int = 0):
    """A query as a function: no session, no I/O, fully testable."""
    return select(Video).where(Video.views >= min_views).order_by(Video.views.desc()).limit(limit)


# --- 1. Rows vs entities: the single most common confusion -------------------
with get_session() as session:
    row = session.execute(select(User).limit(1)).first()
    print("1. execute(...).first() ->", type(row).__name__, row, "| the User is row[0]")

    user = session.scalars(select(User).limit(1)).first()
    print("   scalars().first()   ->", type(user).__name__, user.name)
    print("""
   session.scalars(stmt) == session.execute(stmt).scalars()
   scalars() when you select whole entities, execute() when you select columns.
""")

# --- 2. The result vocabulary ------------------------------------------------
with get_session() as session:
    empty = select(User).where(User.age > 100)
    print("2. .all()          ->", len(session.scalars(select(User)).all()), "users")
    print("   .first()        ->", session.scalars(empty).first(), "-- None, no exception")
    print("   .one_or_none()  ->", session.scalars(empty).one_or_none(), "-- None, or raises if >1")
    try:
        session.scalars(empty).one()
    except NoResultFound:
        print("   .one()          -> NoResultFound")
    try:
        session.scalars(select(User)).one()
    except MultipleResultsFound:
        print("   .one() on many  -> MultipleResultsFound")
    print("   session.scalar()->", session.scalar(select(func.count(Video.id))),
          "-- first column of the first row, or None")

# --- 3. Selecting columns: Rows are named tuples -----------------------------
with get_session() as session:
    rows = session.execute(select(User.name, User.age).where(User.age < 30).order_by(User.age)).all()
    print("\n3. columns come back as Rows:", rows[:2])
    for name, age in rows[:2]:                     # unpack like any tuple
        print(f"   {name} is {age}")
    print("   by attribute:", rows[0].name, "| as a dict:", dict(rows[0]._mapping))

# --- 4. Two entities in one statement ----------------------------------------
with get_session() as session:
    pairs = session.execute(select(User, Video).join(Video).order_by(Video.views.desc()).limit(2)).all()
    print()
    for user, video in pairs:
        print(f"4. {user.name:<28} {video.title[:26]:<28} {video.views:>6}")

# --- 5. A statement is a plain value: build it anywhere, reuse it ------------
with get_session() as session:
    print("\n5. reusable statement:", *(v.title for v in session.scalars(top_videos(2))), sep="\n   ")

    # Statements are immutable: every method returns a new one, so refine safely.
    base = select(Video)
    print("   base is untouched:", len(session.scalars(base).all()),
          "vs refined:", len(session.scalars(base.where(Video.views > 10_000)).all()))

# --- 6. See the SQL ----------------------------------------------------------
# No session at all: rendering a statement to a string never touches the database.
print("\n6. str(stmt):", " ".join(str(top_videos(3, 100)).split()))

drop_db()      # clean up youtube-channels.db
