"""Двигун, схема й сесія для прикладів модуля.

    from db import get_session

    with get_session() as session:
        session.add(User(...))          # коміт сам, на виході з блоку

"""
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import sessionmaker

from models import Base
from seed import seed

# Відносний шлях: три слеші в URL і назва файла -- база з'явиться в тій теці,
# з якої запустили скрипт. Абсолютний шлях мав би чотири слеші (sqlite:////...).
DB_NAME = "youtube-channels.db"
DB_PATH = Path(DB_NAME)

engine = create_engine(f"sqlite:///{DB_NAME}", echo=False)


@event.listens_for(Engine, "connect")
def _sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
    """SQLite ігнорує FOREIGN KEY, поки не попросиш (вимкнено з 2005 року).

    Без цього ondelete="CASCADE" тихо не працює -- а саме на нього посилається
    текст у кінці 07_orm_crud.py.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# Одна фабрика на застосунок...
SessionLocal = sessionmaker(engine)


@contextmanager
def get_session():
    """Commit on a clean exit, roll back on an exception, always close.

    Сесія живе рівно один блок `with` -- одна одиниця роботи. Це та форма, яку
    пишуть у застосунках, замість однієї довгої сесії на весь модуль.

    Ловимо `Exception`, а не `SQLAlchemyError`: відкат коректний за будь-якої
    помилки, навіть якщо вона в нашому Python-коді, а не в базі. `raise` без
    аргументів піднімає те саме виключення з тим самим traceback -- контекстний
    менеджер його не з'їдає, а лише прибирає за собою.

    `finally` закриває сесію в усіх трьох випадках: успіх, помилка, і навіть
    коли з блоку вийшли через return.
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


def drop_db() -> None:
    """Видалити файл бази.

    `engine.dispose()` спершу: поки в пулі є відкрите з'єднання, файл на Windows
    не видалиться, та й лишати engine з посиланням на видалений файл не варто.
    Після drop_db() engine ще робочий -- при наступному запиті він відкриє
    з'єднання знову й SQLite створить порожній файл.
    """
    engine.dispose()
    DB_PATH.unlink(missing_ok=True)


def init_db() -> None:
    """Чиста схема + демо-дані. Викликається при імпорті db.

    drop_all перед create_all -- бо файл лишається між запусками: без цього
    seed() додав би другий комплект рядків і впав на UNIQUE email.
    """
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    # Той самий контекстний менеджер, що й для решти коду: seed() лише додає
    # об'єкти, а коміт і закриття робить get_session().
    with get_session() as session:
        seed(session)


init_db()
print(f"0. {DB_NAME}:", ", ".join(Base.metadata.tables))
