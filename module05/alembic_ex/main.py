"""Демо: код працює з базою, схему якої створив Alembic.

    uv run alembic upgrade head
    uv run python main.py

Якщо запустити main.py на порожній теці (без `upgrade head`), він впаде на
`no such table: authors` -- і це правильна поведінка. Тека alembic_ex ніде не
викликає `create_all()`: таблиці існують рівно тоді, коли міграції накочені.
"""
from sqlalchemy import delete, func, select

from db import get_session
from models import Author, Book, Genre

BOOKS = [
    ("George Orwell", "UK", "1984", 1949, "dystopia"),
    ("George Orwell", "UK", "Animal Farm", 1945, "dystopia"),
    ("Ursula K. Le Guin", "US", "The Dispossessed", 1974, "sci-fi"),
    ("Stanisław Lem", "PL", "Solaris", 1961, "sci-fi"),
]


def main() -> None:
    # Окремий блок -- окрема сесія й окрема транзакція. Читання не зобов'язане
    # жити в тій самій сесії, що й запис.
    with get_session() as session:
        rows = session.execute(
            select(Author.name, func.count(Book.id))
            .join(Author.books)
            .group_by(Author.id)
            .order_by(func.count(Book.id).desc())
        ).all()
        for name, count in rows:
            print(f"{name:20} {count} книг")


if __name__ == "__main__":
    main()
