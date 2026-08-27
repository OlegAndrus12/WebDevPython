"""ORM-моделі: клас -> таблиця .

    uv run 05_orm_models.py
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint, ForeignKey, Index, Numeric, String, UniqueConstraint,
    create_engine, func, inspect,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from models import Base, User, Video


# --- 1. The whole vocabulary you need ------------------------------------------
class Demo(DeclarativeBase):
    """One Base per application; it owns the MetaData every model registers into."""


class Author(Demo):
    __tablename__ = "authors"

    # The annotation gives the type and the nullability.
    id: Mapped[int] = mapped_column(primary_key=True)       # PK -> autoincrement
    name: Mapped[str] = mapped_column(String(120))          # NOT NULL VARCHAR(120)
    bio: Mapped[str | None]                                 # nullable TEXT
    email: Mapped[str] = mapped_column(String(120), unique=True)
    age: Mapped[int] = mapped_column(index=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    active: Mapped[bool] = mapped_column(default=True)
    # default= is computed in Python; server_default= goes into the DDL and is
    # computed by the database (right even for rows inserted by psql or a migration).
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    posts: Mapped[list["Post"]] = relationship(
        back_populates="author", cascade="all, delete-orphan"
    )

    # Table-level things go here: multi-column constraints and indexes.
    __table_args__ = (
        CheckConstraint("age > 10 AND age < 90", name="ck_authors_age"),
        UniqueConstraint("name", "email", name="uq_authors_name_email"),
        Index("ix_authors_active_age", "active", "age"),
    )

    def __repr__(self) -> str:
        return f"<Author #{self.id} {self.name}>"


class Post(Demo):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    # A foreign key without an index is the most common slow-join cause there is.
    author_id: Mapped[int] = mapped_column(
        ForeignKey("authors.id", ondelete="CASCADE"), index=True
    )
    author: Mapped[Author] = relationship(back_populates="posts")


engine = create_engine("sqlite://")
Demo.metadata.create_all(engine)
print("1. tables created  :", inspect(engine).get_table_names())
print("   columns of posts:", [c.name for c in Post.__table__.columns])

video = Video(title="Моделі за 5 хвилин")
print("\n3. Video(...) ->", video)
print("   id     =", video.id, "-- the database assigns it, on INSERT")
print("   views  =", video.views, "-- default=0 is also applied on INSERT, not now")
print("   author =", video.author, "-- an empty relationship, not an error")

Base.metadata.create_all(engine)

print("\n4. models.Base knows:", sorted(Base.metadata.tables))

engine.dispose()
