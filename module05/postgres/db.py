"""Двигун, схема й сесія для прикладів на Postgres.

    from db import get_session

    with get_session() as session:
        session.add(Author(...))        # коміт сам, на виході з блоку
"""
from contextlib import contextmanager
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base

# postgresql+psycopg -> psycopg 3. Дані з compose.yaml: admin/admin, база users.
# Змінюється лише цей рядок — решта коду в модулі не залежить від бази.
URL = os.getenv("DATABASE_URL", "postgresql+psycopg://admin:admin@localhost:5432/users")

# Engine — це пул з'єднань + знання про діалект бази. Один на весь застосунок,
# створюється при старті. З'єднання не відкривається одразу: тільки при першому
# запиті. echo=True друкував би кожен SQL — зручно, коли не розумієш, що пішло в базу.
engine = create_engine(URL, echo=False)

# sessionmaker — фабрика сесій, налаштована один раз. Сама нічого не робить,
# тільки запам'ятовує engine (і опції типу expire_on_commit). Викликаєш
# SessionLocal() — отримуєш нову Session на одну операцію: один запит, один скрипт.
SessionLocal = sessionmaker(engine)


@contextmanager
def get_session():
    """Commit on a clean exit, roll back on an exception, always close.

    Сесія живе рівно один блок `with` -- одна одиниця роботи. Той самий
    контекстний менеджер, що й у ../sqlalchemy/db.py: код секцій нижче не знає,
    що під ним Postgres, а не SQLite.

    Ловимо `Exception`, а не `SQLAlchemyError`: відкат коректний за будь-якої
    помилки, навіть якщо вона в нашому Python-коді, а не в базі. `raise` без
    аргументів піднімає те саме виключення з тим самим traceback.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Чиста схема: drop_all перед create_all.

    Викликається явно з crud.py, а не при імпорті -- на відміну від SQLite-файла,
    тут за томом postgres_data стоїть база, яку ти дивишся в pgAdmin, і затирати
    її самим лише фактом імпорту було б неввічливо.
    """
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


# Більше не потрібно: у compose.yaml є healthcheck, а `up -d --wait` не віддає
# керування, поки база не стане healthy.
#
# def wait_for_db(attempts: int = 15, delay: float = 1.0) -> None:
#     for attempt in range(1, attempts + 1):
#         try:
#             with engine.connect() as conn:
#                 conn.execute(text("SELECT 1"))
#             return
#         except OperationalError:
#             if attempt == attempts:
#                 raise
#             time.sleep(delay)
