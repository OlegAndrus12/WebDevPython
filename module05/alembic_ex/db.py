"""Двигун і сесія. Схему створює Alembic, не цей файл.

    from db import get_session

    with get_session() as session:
        session.add(Author(...))        # коміт сам, на виході з блоку

Відмінність від [../sqlalchemy/db.py](../sqlalchemy/db.py): там при імпорті
йшов `Base.metadata.drop_all()` + `create_all()` + seed. Тут цього немає й бути
не може -- як тільки в проєкті з'явився Alembic, єдиний спосіб змінити схему це
`alembic upgrade`. Два джерела правди на одну базу закінчуються тим, що
`alembic_version` каже одне, а таблиці виглядають інакше.

`DB_URL` імпортує ще й [migrations/env.py](migrations/env.py), щоб адреса бази
була записана в одному місці, а не окремо в коді й окремо в alembic.ini.
"""
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import sessionmaker

# Відносний шлях: три слеші в URL і назва файла -- база з'явиться в тій теці,
# з якої запустили скрипт (тобто поруч з alembic.ini). Абсолютний шлях мав би
# чотири слеші (sqlite:////...).
DB_NAME = "library.db"
DB_PATH = Path(DB_NAME)
DB_URL = f"sqlite:///{DB_NAME}"

engine = create_engine(DB_URL, echo=False)


# Одна фабрика на застосунок...
SessionLocal = sessionmaker(engine)


@contextmanager
def get_session():

    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def drop_db() -> None:
    engine.dispose()
    DB_PATH.unlink(missing_ok=True)
