"""WHERE, ORDER BY, LIMIT: the filtering operators.

Every Python operator on a mapped attribute builds SQL instead of comparing values.
Hence the two rules you must remember:

    `== None` / `.is_(None)`, never `is None`      (`is` cannot be overloaded)
    and_/or_/not_ (or & | ~ with parens), never `and` `or` `not`

Each section gets its own `with get_session()`: one unit of work, one session.
These queries only read, so the sections are independent and the order is free.

    uv run 09_filtering.py
"""
from datetime import datetime

from sqlalchemy import and_, func, or_, select

from db import drop_db, get_session
from models import User, Video


# --- Comparison ---------------------------------------------------------------
# Select the very column you filter on: the output then proves the filter worked.
with get_session() as session:
    print("age == 23        :", session.scalars(select(User.age).where(User.age == 23)).all())
    print("age != 23        :", session.scalars(select(User.age).where(User.age != 23)).all())
    print("age > 30         :", session.scalars(select(User.age).where(User.age > 30)).all())
    print("age BETWEEN 20,30:", session.scalars(select(User.age).where(User.age.between(20, 30))).all())
    print("age IN (22,24,28):", session.scalars(select(User.age).where(User.age.in_([22, 24, 28]))).all())
    print("age NOT IN (...) :", session.scalars(select(User.age).where(User.age.not_in([22, 24, 28]))).all())

# --- Text --------------------------------------------------------------------
with get_session() as session:
    print("\nemail LIKE '%.net':", session.scalars(select(User.email).where(User.email.like("%example.net"))).all())
    print("name LIKE 'J%'    :", session.scalars(select(User.name).where(User.name.like("J%"))).all())
    print("name ILIKE 'j%'   :", session.scalars(select(User.name).where(User.name.ilike("j%"))).all())
    print("name startswith An:", session.scalars(select(User.name).where(User.name.startswith("An"))).all())
    print("name contains 'on':", session.scalars(select(User.name).where(User.name.contains("on"))).all())
    print("length(name) > 15 :", session.scalars(select(User.name).where(func.length(User.name) > 15)).all())
    # ILIKE works here only because the seeded names are ASCII: on SQLite ilike/lower
    # fold ASCII and nothing else, so 'С%' would never match 'село'. On Postgres it
    # would. Worth knowing before you develop on SQLite and deploy on Postgres.

# --- NULL --------------------------------------------------------------------
with get_session() as session:
    print("\nbio IS NULL    :", session.scalars(select(User.bio).where(User.bio.is_(None))).all())
    print("bio IS NOT NULL:", len(session.scalars(select(User.bio).where(User.bio.is_not(None))).all()), "rows")
    print("User.bio.is_(None) ->", User.bio.is_(None), " <- SQL")
    print("User.bio is None   ->", User.bio is None, " <- a Python bool. Always wrong.")

# --- Combining ---------------------------------------------------------------
with get_session() as session:
    # Several .where() calls are ANDed -- the most readable form.
    print("\ntwo .where() = AND:", session.scalars(
        select(Video.views).where(Video.views > 5000).where(Video.likes > 500).limit(6)
    ).all(), "(first 6)")
    print("and_(...)         :", session.scalars(
        select(Video.views).where(and_(Video.views > 5000, Video.likes > 500)).limit(6)
    ).all(), "-- identical to the two .where() above")
    print("or_(...)          :", session.scalars(
        select(Video.views).where(or_(Video.views > 15_000, Video.likes > 3000)).limit(6)
    ).all(), "(first 6)")
    print("nested and_/or_   :", len(session.scalars(
        select(Video.id).where(and_(Video.views > 1000, or_(Video.likes > 2000, Video.title.like("S%"))))
    ).all()), "rows")
    print("~ (NOT), parens   :", len(session.scalars(
        select(Video.id).where(~Video.title.like("%one%"))
    ).all()), "rows")

# --- Dates -------------------------------------------------------------------
with get_session() as session:
    print("\nuploaded >= 2025-06-01:", session.scalars(
        select(func.date(Video.uploaded_on)).where(Video.uploaded_on >= datetime(2025, 6, 1)).limit(5)
    ).all(), "(first 5)")
    print("uploaded in Q1 2025   :", session.scalars(
        select(func.date(Video.uploaded_on)).where(
            Video.uploaded_on.between(datetime(2025, 1, 1), datetime(2025, 3, 31))
        ).limit(5)
    ).all(), "(first 5)")
    a_day = session.scalar(select(Video.uploaded_on)).date().isoformat()
    print(f"date(uploaded_on) == '{a_day}':", len(session.scalars(
        select(Video.id).where(func.date(Video.uploaded_on) == a_day)
    ).all()), "rows")

# --- filter_by: keyword shorthand for equality -------------------------------
with get_session() as session:
    print("\nfilter_by(age=23):", session.scalars(select(User.age).filter_by(age=23)).all())

# --- Ordering, limit, offset, distinct ---------------------------------------
with get_session() as session:
    top = session.scalars(select(Video).order_by(Video.views.desc()).limit(3)).all()
    print("\ntop 3 by views:", *[f"{v.views:>6}  {v.title[:36]}" for v in top], sep="\n  ")
    print("two keys      :", session.scalars(
        select(User.name).order_by(User.age.desc(), User.name).limit(2)
    ).all())
    print("page 2 of 3   :", session.scalars(select(User.id).order_by(User.id).limit(3).offset(3)).all())
    print("distinct ages :", sorted(session.scalars(select(User.age).distinct()).all()))
    # OFFSET makes the database count and throw away rows: page 10 000 is slow no
    # matter what. For deep paging, order by an indexed column and use
    # .where(User.id > last_seen_id) instead.

drop_db()      # clean up youtube-channels.db
