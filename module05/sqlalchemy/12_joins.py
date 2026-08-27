"""JOIN: along a relationship, on a condition, OUTER — and what aliased is for.

Each section gets its own `with get_session()`.

    uv run 12_joins.py
"""
from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from db import drop_db, get_session
from models import Tag, User, Video

# --- 1. join() finds the ON clause from the ForeignKey ------------------------
with get_session() as session:
    rows = session.execute(
        select(User.name, Video.title).join(Video).order_by(Video.views.desc()).limit(3)
    ).all()
    print("1. join(Video):")
    for name, title in rows:
        print(f"   {name:<28} {title[:34]}")

    # Naming the relationship is clearer, and required once two FKs could match.
    same = session.execute(select(User.name, Video.title).join(User.videos).limit(1)).all()
    print("   join(User.videos) is the same thing:", same)

# --- 2. Whole entities, not columns ------------------------------------------
with get_session() as session:
    pairs = session.execute(select(User, Video).join(Video).limit(2)).all()
    print("\n2. two entities per Row:", [(u.name, v.views) for u, v in pairs])

    # Selecting only User over a join can repeat authors -- one row per video.
    authors = session.scalars(select(User).join(Video)).all()
    distinct = session.scalars(select(User).join(Video).distinct()).all()
    print("   select(User).join(Video):", len(authors), "rows ->", len(distinct), "with .distinct()")
    print("   (for a plain filter, prefer .where(User.videos.any(...)): EXISTS, no dupes)")

# --- 3. Filtering across the join --------------------------------------------
with get_session() as session:
    popular = session.execute(
        select(User.name, Video.title, Video.views)
        .join(Video)
        .where(User.age < 40, Video.views > 10_000)
        .order_by(Video.views.desc())
    ).all()
    print(f"\n3. authors under 40 with a >10k video: {len(popular)} rows, e.g. {popular[0]}")

# --- 4. outerjoin keeps the left side ----------------------------------------
with get_session() as session:
    left = session.execute(
        select(User.name, func.count(Video.id).label("n")).outerjoin(Video).group_by(User.id).order_by("n")
    ).all()
    print("\n4. outerjoin:", left[:2], "-- 0 for the author with no videos")

# --- 5. Chaining joins: User -> Video -> Tag ---------------------------------
with get_session() as session:
    tagged = session.scalars(
        select(User).join(User.videos).join(Video.tags).where(Tag.name == "python").distinct()
    ).all()
    print("\n5. authors with a 'python' video:", [u.name for u in tagged])

# --- 6. An explicit ON condition ---------------------------------------------
with get_session() as session:
    cross = session.execute(
        select(User.name, Video.title)
        .join(Video, (Video.author_id == User.id) & (Video.views > 15_000))
        .limit(2)
    ).all()
    print("\n6. join(Video, <condition>):", cross)

# --- 7. aliased: the same table twice in one statement -----------------------
with get_session() as session:
    # Without an alias, SQL cannot tell the two copies of `videos` apart.
    a, b = aliased(Video), aliased(Video)
    same_author_pairs = session.execute(
        select(a.title, b.title)
        .join(b, (a.author_id == b.author_id) & (a.id < b.id))
        .limit(2)
    ).all()
    print("\n7. aliased -> two videos by the same author:", same_author_pairs)

drop_db()      # clean up youtube-channels.db
