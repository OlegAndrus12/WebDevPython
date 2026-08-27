"""CRUD на Postgres: створити, прочитати з фільтром, відсортувати, порахувати.

Кожна секція -- свій `with get_session()`: одна одиниця роботи, одна сесія.
Комітить контекстний менеджер на виході з блоку, тому `session.commit()` у коді
секцій немає. Наслідок, який видно нижче: об'єкт із попередньої секції в
наступній уже недоступний -- його треба дістати з бази знову.

    docker compose up -d --wait
    uv run crud.py
"""
import json
from pathlib import Path

from sqlalchemy import delete, func, select, update

from db import engine, get_session, init_db
from models import Author, Book

init_db()

LE_GUIN = "leguin@example.com"
ATWOOD = "atwood@example.com"

# Дані лежать поруч у authors.json. Path(__file__).parent, а не відносний шлях:
# інакше файл знайдеться лише коли запускати з цієї теки.
# Кількість книжок в авторів різна навмисно: HAVING нижче має відсіювати частину
# груп, інакше він нічого не демонструє.
AUTHORS = json.loads((Path(__file__).parent / "authors.json").read_text(encoding="utf-8"))


# --- CREATE -------------------------------------------------------------------
with get_session() as session:
    for row in AUTHORS:
        # Ключі в JSON названі як колонки, тому Book(**book) складається сам.
        # Книжки їдуть разом з автором: save-update cascade. FK author_id
        # проставляє relationship, руками його ніхто не присвоює.
        books = [Book(**book) for book in row["books"]]
        session.add(Author(name=row["name"], email=row["email"], city=row["city"], books=books))

with get_session() as session:
    print("CREATE")
    print("  authors:", session.scalar(select(func.count(Author.id))))
    print("  books  :", session.scalar(select(func.count(Book.id))))


# --- READ ---------------------------------------------------------------------
with get_session() as session:
    # Нова сесія: об'єкт із попереднього блоку тут не працює, дістаємо заново.
    le_guin = session.scalars(select(Author).where(Author.email == LE_GUIN)).one()

    print("\nREAD")
    print("  by id      :", session.get(Author, 1))
    print("  all authors:", session.scalars(select(Author.name)).all())
    print("  one book   :", session.scalars(select(Book).where(Book.title == "Foundation")).one())
    print("  her books  :", [b.title for b in le_guin.books])


# --- FILTER -------------------------------------------------------------------
with get_session() as session:
    print("\nFILTER")
    print("  year > 1990     :", session.scalars(select(Book.title).where(Book.year > 1990)).all())
    print("  price 200..300  :", session.scalars(select(Book.price).where(Book.price.between(200, 300))).all())
    print("  title LIKE 'The%':", session.scalars(select(Book.title).where(Book.title.like("The%"))).all())
    print("  city IN (...)   :", session.scalars(
        select(Author.name).where(Author.city.in_(["London", "Toronto"]))
    ).all())
    # ILIKE on Postgres is genuinely case-insensitive -- lowercase 'u' finds 'Ursula'.
    print("  name ILIKE 'u%' :", session.scalars(select(Author.name).where(Author.name.ilike("u%"))).all())
    print("  join + filter   :", session.scalars(
        select(Book.title).join(Author).where(Author.city == "London")
    ).all())


# --- SORT ---------------------------------------------------------------------
with get_session() as session:
    print("\nSORT")
    print("  cheapest first :", session.scalars(select(Book.price).order_by(Book.price).limit(5)).all())
    print("  newest first   :", session.scalars(select(Book.year).order_by(Book.year.desc()).limit(5)).all())
    print("  top 2 by price :", session.scalars(select(Book).order_by(Book.price.desc()).limit(2)).all())
    print("  two keys       :", session.scalars(
        select(Book.title).order_by(Book.year.desc(), Book.title).limit(4)
    ).all())


# --- AGGREGATE ----------------------------------------------------------------
with get_session() as session:
    print("\nAGGREGATE")
    print("  count    :", session.scalar(select(func.count(Book.id))))
    print("  sum      :", session.scalar(select(func.sum(Book.price))))
    print("  avg      :", session.scalar(select(func.round(func.avg(Book.price), 2))))
    print("  min / max:", session.scalar(select(func.min(Book.year))),
          "/", session.scalar(select(func.max(Book.year))))

    per_author = session.execute(
        select(Author.name, func.count(Book.id).label("books"), func.sum(Book.price).label("total"))
        .join(Book)
        .group_by(Author.id)
        .order_by(func.sum(Book.price).desc())
    ).all()
    print("  GROUP BY author:")
    for name, books, total in per_author:
        print(f"    {name:<22} {books} books  ${total}")

    many = session.execute(
        select(Author.name, func.count(Book.id).label("n"))
        .join(Book)
        .group_by(Author.id)
        .having(func.count(Book.id) >= 3)
    ).all()
    print("  HAVING >= 3 books:", [name for name, _ in many])


# --- UPDATE -------------------------------------------------------------------
with get_session() as session:
    print("\nUPDATE")
    book = session.scalars(select(Book).where(Book.title == "Foundation")).one()
    book.price = 999                # просто присвоєння, сесія сама помітить
    session.flush()
    print("  one object :", book.title, "->", book.price)

    # Один запит на багато рядків: без об'єктів у пам'яті й без циклу в Python.
    rows = session.execute(update(Book).where(Book.year < 1970).values(price=Book.price + 50))
    print("  bulk       :", rows.rowcount, "rows published before 1970 got +50")


# --- DELETE -------------------------------------------------------------------
with get_session() as session:
    print("\nDELETE")
    atwood = session.scalars(select(Author).where(Author.email == ATWOOD)).one()
    print("  deleting   :", atwood.name, "with", len(atwood.books), "books")
    session.delete(atwood)          # cascade removes their books too
    session.flush()
    print("  left       :", session.scalar(select(func.count(Author.id))), "authors,",
          session.scalar(select(func.count(Book.id))), "books")

    rows = session.execute(delete(Book).where(Book.price < 250))
    print("  bulk       :", rows.rowcount, "cheap books deleted |",
          session.scalar(select(func.count(Book.id))), "books left")


engine.dispose()
