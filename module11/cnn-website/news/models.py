from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, MetaData, String, Text, false, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Role(StrEnum):
    """What a user is allowed to reach. Switched by hand in pgAdmin."""

    USER = "user"
    ADMIN = "admin"


NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """One Base per application. It owns the MetaData Alembic compares against."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Source(Base):
    """A NewsAPI source: cnn, bbc-news, reuters."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(120))

    articles: Mapped[list[Article]] = relationship(back_populates="source")

    def __repr__(self) -> str:
        return f"<Source {self.slug}>"


class Article(Base):
    """One story. NewsAPI issues no stable id, so `url` is the natural key."""

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str] = mapped_column(String(1000), unique=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text())
    content: Mapped[str | None] = mapped_column(Text())
    image_url: Mapped[str | None] = mapped_column(String(1000))
    author: Mapped[str | None] = mapped_column(String(200))
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )

    source: Mapped[Source] = relationship(back_populates="articles")

    def __repr__(self) -> str:
        return f"<Article #{self.id} {self.title[:40]!r}>"


class User(Base):
    """A registered reader."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(150), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    confirmed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )

    subscribed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )

    role: Mapped[Role] = mapped_column(
        Enum(
            Role,
            name="user_role",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=Role.USER,
        server_default=Role.USER.value,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<User {self.username} {'confirmed' if self.confirmed else 'unconfirmed'}>"


class LikedArticle(Base):
    """One (user, article) like. No relationship()/secondary=: liked-articles"""

    __tablename__ = "liked_articles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True
    )
    liked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<LikedArticle user={self.user_id} article={self.article_id}>"
