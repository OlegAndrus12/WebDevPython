"""Моделі для прикладів з Alembic.

    authors ---1:M--- books ---M:1--- genres

    Author 1 : M  Book    author.books <-> book.author  FK books.author_id
    Genre  1 : M  Book    genre.books  <-> book.genre   FK books.genre_id

Схему тут ніхто не створює: `Base.metadata.create_all()` у цій теці не
викликається жодного разу. Таблиці з'являються тільки через міграції, а
`Base.metadata` потрібна Alembic'у як "як має бути" -- з нею він порівнює
реальну базу під час `alembic revision --autogenerate`.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, MetaData, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """One Base per application. It owns the MetaData Alembic compares against."""

    metadata = MetaData()


class Author(Base):
    __tablename__ = "authors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    country: Mapped[str | None] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    books: Mapped[list[Book]] = relationship(
        back_populates="author", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Author #{self.id} {self.name}>"


class Genre(Base):
    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40), unique=True)

    books: Mapped[list[Book]] = relationship(back_populates="genre")

    def __repr__(self) -> str:
        return f"<Genre {self.name}>"


class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    year: Mapped[int]
    pages: Mapped[int | None]
    isbn: Mapped[str | None] = mapped_column(String(17), unique=True)
    author_id: Mapped[int] = mapped_column(
        ForeignKey("authors.id", ondelete="CASCADE"), index=True
    )
    genre_id: Mapped[int | None] = mapped_column(ForeignKey("genres.id", ondelete="SET NULL"))

    author: Mapped[Author] = relationship(back_populates="books")
    genre: Mapped[Genre | None] = relationship(back_populates="books")

    def __repr__(self) -> str:
        return f"<Book #{self.id} {self.title!r} ({self.year})>"
