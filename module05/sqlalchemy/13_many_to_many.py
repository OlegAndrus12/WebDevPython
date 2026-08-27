"""Many-to-many: secondary=, and when you need an association object.

A video has many tags; a tag belongs to many videos. There is no such column, so
the link lives in a third table with two foreign keys.

    secondary=          the link table is plumbing, invisible in Python
    association object  the link is a model, because it has columns of its own

Each section gets its own `with get_session()`.

    uv run 14_many_to_many.py
"""
from sqlalchemy import func, select

from db import drop_db, get_session
from models import Tag, User, Video, VideoTag


def links(session) -> int:
    return session.scalar(select(func.count()).select_from(VideoTag))


def any_tagged_video(session) -> Video:
    return session.scalars(select(Video).where(Video.tags.any())).first()


# --- 1. Both sides read like a list -------------------------------------------
with get_session() as session:
    video = any_tagged_video(session)
    print(f"1. {video.title[:30]!r} -> {[t.name for t in video.tags]}")

    python = session.scalars(select(Tag).where(Tag.name == "python")).one()
    print(f"   tag 'python' -> {len(python.videos)} videos, e.g. {python.videos[0].title[:30]!r}")

# --- 2. Linking is list manipulation; SQLAlchemy writes the link rows ---------
with get_session() as session:
    video = any_tagged_video(session)
    docker = session.scalars(select(Tag).where(Tag.name == "docker")).one()
    print("\n2. rows in video_tag:", links(session))
    if docker not in video.tags:
        video.tags.append(docker)
        session.flush()
        print("   after append   :", links(session), "-- an INSERT into the link table")
    video.tags.remove(docker)
    session.flush()
    print("   after remove   :", links(session), "-- a DELETE. You never touch video_tag yourself.")
    session.rollback()

# --- 3. Querying across the link ----------------------------------------------
with get_session() as session:
    tagged = session.scalars(select(Video).where(Video.tags.any(Tag.name == "async"))).all()
    print(f"\n3. videos tagged 'async': {len(tagged)}")

    # Two tags at once needs two EXISTS: one join would ask a single row to have two
    # different tag names at the same time, which no row can.
    both = session.scalars(
        select(Video).where(Video.tags.any(Tag.name == "python")).where(Video.tags.any(Tag.name == "sql"))
    ).all()
    print(f"   tagged BOTH python and sql: {len(both)}")

    popularity = session.execute(
        select(Tag.name, func.count(Video.id).label("n"))
        .join(Tag.videos)                     # join along the relationship, link table included
        .group_by(Tag.id)
        .order_by(func.count(Video.id).desc())
    ).all()
    print("   tag popularity:", popularity)

    authors = session.scalars(
        select(User).join(User.videos).join(Video.tags).where(Tag.name == "live").distinct()
    ).all()
    print("   authors with a 'live' video:", [u.name for u in authors])



drop_db()      # clean up youtube-channels.db
