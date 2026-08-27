"""Relationships: one-to-many, many-to-one, any()/has() and cascade.

A ForeignKey is a database constraint; a relationship() is the Python attribute
built on top of it. You declare both. Once you have, you stop assigning foreign
keys by hand:

    user.videos.append(video)     # SQLAlchemy fills in video.author_id
    video.author = user           # the other direction, same effect

Each section gets its own `with get_session()`. The flush()/rollback() demos only
gain from that: a rollback stays inside its block and never reaches the next one.

    uv run 11_relationships.py
"""
from sqlalchemy import func, select

from db import drop_db, get_session
from models import User, Video


def any_author(session) -> User:
    """The first author who has videos -- each section loads one in its own session."""
    return session.scalars(select(User).where(User.videos.any())).first()


# --- 1. Navigating both directions --------------------------------------------
with get_session() as session:
    user = any_author(session)
    print(f"1. {user.name} has {len(user.videos)} videos; first is {user.videos[0].title!r}")
    print("   and back:", user.videos[0].author is user, "-- the same object, via the identity map")

# --- 2. back_populates works in memory, before any SQL ------------------------
with get_session() as session:
    user = any_author(session)
    fresh = Video(title="Just created", views=0, likes=0)
    user.videos.append(fresh)
    print("\n2. after append -> author =", fresh.author.name, "| author_id =", fresh.author_id)
    session.flush()
    print("   after flush  -> author_id =", fresh.author_id, "(now the DB has it)")
    session.rollback()

    # The other direction does the same thing. Note the session.add(): assigning the
    # many-to-one side does not put a brand-new object into the Session, appending to
    # user.videos does (that is the save-update cascade).
    user = any_author(session)
    other = Video(title="The other way round", views=0, likes=0)
    other.author = user
    session.add(other)
    session.flush()
    print("   video.author = user -> in user.videos:", other in user.videos)
    session.rollback()

# --- 3. Filtering on a relationship: any() / has() ----------------------------
with get_session() as session:
    # any() for a collection (one-to-many), has() for a scalar (many-to-one).
    # Both render as EXISTS: no join, so no duplicate rows.
    loud = session.scalars(select(User).where(User.videos.any(Video.views > 15_000))).all()
    print("\n3. authors with a >15k video:", [u.name for u in loud])
    silent = session.scalars(select(User).where(~User.videos.any())).all()
    print("   authors with no videos    :", [u.name for u in silent])
    young = session.scalars(select(Video).where(Video.author.has(User.age < 25))).all()
    print("   videos by authors under 25:", len(young))

# --- 4. Counting a collection without loading it ------------------------------
with get_session() as session:
    # len(user.videos) loads every row. If you only need the number, ask SQL.
    counted = session.execute(
        select(User.name, func.count(Video.id)).outerjoin(Video).group_by(User.id).order_by(User.id)
    ).all()
    print("\n4. counts, no objects loaded:", counted[:3])

# --- 5. cascade: what happens to the children ---------------------------------
with get_session() as session:
    victim = any_author(session)
    n = len(victim.videos)
    name = victim.name                  # read it before the delete: the rollback would expire the object
    session.delete(victim)
    session.flush()
    print(f"\n5. deleted {name} ({n} videos) -> videos left:",
          session.scalar(select(func.count(Video.id))))
    print("""   Two independent mechanisms, and you want both:
     cascade="all, delete-orphan"   -- the ORM deletes the children it loaded
     ondelete="CASCADE" on the FK   -- the DATABASE deletes them, even the rows
                                       the ORM never loaded (bulk deletes, psql)
   With neither: an IntegrityError, or orphan rows.""")
    session.rollback()

# --- 6. delete-orphan: removing a child deletes the row -----------------------
with get_session() as session:
    user = any_author(session)
    gone = user.videos.pop()
    gone_id, gone_title = gone.id, gone.title
    session.flush()
    print(f"\n6. popped {gone_title!r} -> row deleted:", session.get(Video, gone_id) is None)
    session.rollback()

drop_db()      # clean up youtube-channels.db
