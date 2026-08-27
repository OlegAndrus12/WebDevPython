from sqlalchemy import delete, func, insert, select, update

from db import drop_db, get_session
from models import User, Video, VideoTag


# --- CREATE -------------------------------------------------------------------
with get_session() as session:
    print(session.scalars(select(User).where(User.email == "olena@example.com")).all())
    user = User(name="Olena Tkach", email="olena@example.com", age=31)
    print(session.scalars(select(User).where(User.email == "olena@example.com")).all())
    session.add(user)
    print(session.scalars(select(User).where(User.email == "olena@example.com")).all())
    session.commit()                    # explicit: the next line reads the id
    print(session.scalars(select(User).where(User.email == "olena@example.com")).all())

    print("1. add()      -> id =", user.id, "(read back after commit)")
    print(session.scalar(select(func.count()).select_from(User)))
    session.add_all([
        User(name="Petro Hnat", email="petro@example.com", age=45),
        User(name="Iryna Luts", email="iryna@example.com", age=22),
    ])
    print("   add_all()  -> users =", session.scalar(select(func.count()).select_from(User)))

    session.commit()
    print("   add_all()  -> users =", session.scalar(select(func.count()).select_from(User)))

    # Children through the relationship: you never set author_id by hand.
    user.videos.append(Video(title="ORM in 10 minutes", views=120, likes=9))
    session.commit()
    print("   via relationship -> author_id =", user.videos[-1].author_id)

    # Thousands of rows with no objects to track: insert() with a list of dicts.
    session.execute(insert(Video), [
        {"title": f"Batch video {i}", "views": i * 10, "likes": i, "author_id": user.id}
        for i in range(1, 4)
    ])

# --- READ ---------------------------------------------------------------------
with get_session() as session:
    print("\n2. get(User, 1)        :", session.get(User, 1))
    print("   one()               :", session.scalars(select(User).where(User.email == "olena@example.com")).one())
    print("   first()             :", session.scalars(select(User).order_by(User.age)).first())
    print("   all() (2 of them)   :", session.scalars(select(User).limit(2)).all())
    print("   one column          :", session.scalar(select(User.name).where(User.id == 1)))
    print("   exists?             :", session.scalar(select(User.id).where(User.age > 100)) is not None)

# --- UPDATE -------------------------------------------------------------------
with get_session() as session:
    # A new session: the object from the CREATE block is gone, so fetch it again.
    user = session.scalars(select(User).where(User.email == "olena@example.com")).one()
    user.age = 32                       # just assign; the Session notices
    user.name = "Olena Tkach-Melnyk"
    session.commit()
    print("\n3. attribute assignment ->", session.get(User, user.id))

with get_session() as session:
    # One statement for many rows -- no objects loaded, no Python loop.
    result = session.execute(update(Video).where(Video.views < 100).values(views=Video.views + 1000))
    print("   update(...) rowcount:", result.rowcount, "-- and views=views+1000 ran in SQL")

with get_session() as session:
    # Per-primary-key updates in one round trip.
    session.execute(update(User), [{"id": 1, "age": 33}, {"id": 2, "age": 46}])
    print("   bulk update by pk   :", session.scalars(select(User.age).order_by(User.id).limit(2)).all())

# --- DELETE -------------------------------------------------------------------
# Delete the object: the ORM issues a DELETE for every child it can see.
with get_session() as session:
    # The user with the most videos, so the cascade below is visible in the counts.
    victim = session.scalars(
        select(User).join(Video).group_by(User.id).order_by(func.count(Video.id).desc())
    ).first()
    print(f"\n4. deleting {victim} with {len(victim.videos)} videos")
    print("   before            : videos =", session.scalar(select(func.count()).select_from(Video)),
          "| video_tag =", session.scalar(select(func.count()).select_from(VideoTag)))

    session.delete(victim)              # cascade removes their videos too
    #flush() forces SQLAlchemy to execute pending SQL
    session.flush()                     # so the count() below sees the delete

    print("   after             : videos =", session.scalar(select(func.count()).select_from(Video)),
          "| video_tag =", session.scalar(select(func.count()).select_from(VideoTag)))

# Remove a user by id -- two ways.
with get_session() as session:
    # get() first: returns None when there is no such row, so you can tell
    # "already deleted" from "never existed" before touching anything.
    user = session.get(User, 2)
    print(f"\n5. get(User, 2)      : {user} with {len(user.videos)} videos")
    print("   before             : users =", session.scalar(select(func.count()).select_from(User)),
          "| videos =", session.scalar(select(func.count()).select_from(Video)))

    session.delete(user)
    session.commit()

    print("   after delete(obj)  : users =", session.scalar(select(func.count()).select_from(User)),
          "| videos =", session.scalar(select(func.count()).select_from(Video)))
    # The clearest proof the row is gone: ask for it again.
    print("   get(User, 2) again :", session.get(User, 2), "-- the row is gone")

    # One statement, no object loaded. The ORM never sees the videos -- they go
    # only because ondelete="CASCADE" is on videos.author_id (and PRAGMA
    # foreign_keys=ON in db.py; without it SQLite silently keeps orphans).
    result = session.execute(delete(User).where(User.id == 3))
    print("   delete(id == 3)    : rowcount =", result.rowcount,
          "| users =", session.scalar(select(func.count()).select_from(User)),
          "| videos =", session.scalar(select(func.count()).select_from(Video)))

    # An id that is not there is not an error, just rowcount 0.
    gone = session.execute(delete(User).where(User.id == 9999))
    print("   delete(id == 9999) : rowcount =", gone.rowcount, "-- no exception")

# Bulk delete by condition.
with get_session() as session:
    result = session.execute(delete(Video).where(Video.views < 200))
    print("\n6. delete(views<200) : rowcount =", result.rowcount,
          "| videos =", session.scalar(select(func.count()).select_from(Video)))

# Both blocks above cleaned up videos and video_tag rows, by two independent
# mechanisms -- and a real project wants both:
#
#   cascade="all, delete-orphan"  on User.videos  -> the ORM deletes loaded children
#   ondelete="CASCADE"            on the FK       -> the DATABASE deletes them, even
#                                                    the rows the ORM never loaded
#
# With neither: IntegrityError, or orphan videos pointing at a user that is gone.
# Statement style also skips the rest of the ORM: no Python default=, and objects
# already in this Session are not refreshed. That is the point -- it is fast.

drop_db()      # clean up youtube-channels.db
