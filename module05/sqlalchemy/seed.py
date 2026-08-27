"""Передбачувані демо-дані для файлів 05-14.

Робить рівно одне: додає об'єкти в сесію. Двигун, схема, коміт і закриття
сесії -- у [db.py](db.py); зовнішні ключі проставляє relationship, руками їх
тут ніхто не присвоює.

Every ORM example starts from the same ten users, ~30 videos and six tags, so
the printed output of one file can be compared with another.

Everything comes from one seeded Faker -- `random` is not imported at all. Faker
has its own generator (`fake.random_int`, `fake.random_elements`,
`fake.date_time_between_dates`), and `Faker.seed()` fixes it, so two runs produce
identical rows.

    from db import get_session
    with get_session() as session:
        ...
"""
from __future__ import annotations

from datetime import datetime

from faker import Faker
from sqlalchemy.orm import Session

from models import Tag, User, Video

TAGS = ["python", "sql", "async", "docker", "tutorial", "live"]
USERS = 10

# Absolute bounds, not "останні 300 днів": a window relative to today would make
# the rows change every morning, and the examples print `uploaded_on`.
FIRST_UPLOAD = datetime(2025, 1, 1)
LAST_UPLOAD = datetime(2025, 10, 31)


def seed(session: Session) -> None:
    fake = Faker("en_US")
    # Without this every run invents new names and ages, and any example that
    # filters on a literal ("age == 23") randomly matches nothing.
    Faker.seed(7)

    tags = [Tag(name=name) for name in TAGS]
    session.add_all(tags)

    for i in range(USERS):
        user = User(
            name=fake.name(),
            # fake.unique -- email is UNIQUE in the model, and a plain
            # fake.email() repeats sooner than you would think.
            email=fake.unique.email(),
            age=fake.random_int(18, 65),
            # Left NULL for most users on purpose: it is the only nullable
            # column, so IS NULL / IS NOT NULL have something to show.
            bio=fake.sentence(nb_words=8) if i % 3 == 0 else None,
        )
        # The last user gets no videos on purpose: without one such row the
        # difference between JOIN and OUTER JOIN is invisible (see file 10).
        videos = 0 if i == USERS - 1 else fake.random_int(1, 5)
        for _ in range(videos):
            views = fake.random_int(50, 20_000)
            video = Video(
                title=fake.sentence(nb_words=4),
                views=views,
                likes=fake.random_int(0, views // 4),
                uploaded_on=fake.date_time_between_dates(FIRST_UPLOAD, LAST_UPLOAD),
                # M:M -- unique=True so one video never gets the same tag twice
                # (the video_tag PK would reject it). SQLAlchemy inserts the
                # link rows itself.
                tags=fake.random_elements(tags, length=fake.random_int(1, 3), unique=True),
            )
            # Appending to the relationship is what sets author_id -- you never
            # assign the foreign key by hand in ORM code.
            user.videos.append(video)
        session.add(user)
