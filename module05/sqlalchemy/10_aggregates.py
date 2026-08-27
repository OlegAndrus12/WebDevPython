"""Aggregates: func, GROUP BY, HAVING — the database counts, not Python.

The rule this file exists to teach: if SQL can express it, do not pull rows into
Python to loop over them. `func.<anything>` renders as a SQL function call, so you
are never limited to what SQLAlchemy happens to know about.

Each section gets its own `with get_session()`.

    uv run 10_aggregates.py
"""
from sqlalchemy import desc, func, select

from db import drop_db, get_session
from models import User, Video

# --- 1. Scalar aggregates: one number out ------------------------------------
with get_session() as session:
    print("1. count(*)       :", session.scalar(select(func.count()).select_from(Video)))
    print("   count(col)     :", session.scalar(select(func.count(Video.id))), "-- ignores NULLs")
    print("   count(distinct):", session.scalar(select(func.count(func.distinct(Video.author_id)))))
    print("   sum            :", session.scalar(select(func.sum(Video.views))))
    print("   avg            :", f"{session.scalar(select(func.avg(Video.likes))):.1f}")
    print("   min / max      :", session.scalar(select(func.min(Video.views))),
          "/", session.scalar(select(func.max(Video.views))))

# --- 2. Several aggregates in one round trip ---------------------------------
with get_session() as session:
    # One Row, not five queries.
    stats = session.execute(
        select(
            func.count(Video.id).label("n"),
            func.sum(Video.views).label("views"),
            func.round(func.avg(Video.views), 1).label("avg"),
        )
    ).one()
    print("\n2. one query, three numbers:", dict(stats._mapping))

# --- 3. GROUP BY: one row per group ------------------------------------------
with get_session() as session:
    per_author = session.execute(
        select(
            User.name,
            func.count(Video.id).label("videos"),
            func.sum(Video.views).label("views"),
        )
        .join(Video)                     # INNER JOIN: authors with no video vanish
        .group_by(User.id)               # group by the PK, not the name: names collide
        .order_by(desc("views"))         # you can order by a label
    ).all()
    print("\n3. per author:")
    for name, videos, views in per_author:
        print(f"   {name:<28} {videos} videos {views:>7} views")

# --- 4. WHERE filters rows, HAVING filters groups ----------------------------
with get_session() as session:
    prolific = session.execute(
        select(User.name, func.count(Video.id).label("n"))
        .join(Video)
        .where(Video.views > 1000)          # which rows go into the groups
        .group_by(User.id)
        .having(func.count(Video.id) >= 3)  # which groups survive
    ).all()
    print("\n4. >=3 videos over 1000 views:", prolific)

# --- 5. Keeping the empty groups: LEFT OUTER JOIN ----------------------------
with get_session() as session:
    all_authors = session.execute(
        select(User.name, func.count(Video.id).label("n"))
        .outerjoin(Video)
        .group_by(User.id)
        .order_by("n")
    ).all()
    print("5. outerjoin keeps the author with 0 videos:", all_authors[:3])

# --- 6. Group by an expression -----------------------------------------------
with get_session() as session:
    by_month = session.execute(
        select(func.strftime("%Y-%m", Video.uploaded_on).label("month"), func.count(Video.id))
        .group_by("month")
        .order_by("month")
    ).all()
    print("6. videos per month:", by_month[:4], "-- strftime is SQLite-only; portability is on you")

# --- 7. What NOT to do -------------------------------------------------------
with get_session() as session:
    in_python = sum(v.views for v in session.scalars(select(Video)))
    in_sql = session.scalar(select(func.sum(Video.views)))
    loaded = session.scalar(select(func.count(Video.id)))
    print(f"\n7. same answer ({in_python} == {in_sql}), but the first one loaded {loaded}")
    print("   objects into memory to add up one column. At 30M rows it is an outage.")

drop_db()      # clean up youtube-channels.db
