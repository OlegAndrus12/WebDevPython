"""Спільні ORM-моделі для файлів 05-14.

Users publish videos, videos carry tags, every relationship kind on one page:

    users ---1:M--- videos ---M:M--- tags
                       (link table: video_tag)

    User  1 : M  Video    user.videos  <-> video.author   FK videos.author_id
    Video M : M  Tag      video.tags   <-> tag.videos     through video_tag
    VideoTag  is that link: M:1 to Video and M:1 to Tag, PK on both FKs
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """One Base per application. It owns the MetaData every model registers into."""


class VideoTag(Base):
    """The M:M link between videos and tags (M:1 to each), as an ordinary model."""

    __tablename__ = "video_tag"

    video_id: Mapped[int] = mapped_column(
        ForeignKey("videos.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[int] = mapped_column(
        ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )

    def __repr__(self) -> str:
        return f"<VideoTag video={self.video_id} tag={self.tag_id}>"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(120), unique=True)
    age: Mapped[int]
    bio: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # 1:M -- one user, many videos. Mapped[list[...]] is the "many" side.
    videos: Mapped[list[Video]] = relationship(
        back_populates="author",
        # delete-orphan: a Video removed from user.videos is deleted, not orphaned.
        cascade="all, delete-orphan",
    )

    __table_args__ = (CheckConstraint("age > 10 AND age < 90", name="ck_users_age"),)

    def __repr__(self) -> str:
        return f"<User #{self.id} {self.name} ({self.age})>"


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    views: Mapped[int] = mapped_column(default=0)
    likes: Mapped[int] = mapped_column(default=0)
    uploaded_on: Mapped[datetime] = mapped_column(default=datetime.now)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    author: Mapped[User] = relationship(back_populates="videos")
    # M:M -- through video_tag.
    tags: Mapped[list[Tag]] = relationship(secondary=VideoTag.__table__, back_populates="videos")

    def __repr__(self) -> str:
        return f"<Video #{self.id} {self.title!r} views={self.views}>"


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40), unique=True)

    # M:M -- the other half of Video.tags, same link table.
    videos: Mapped[list[Video]] = relationship(secondary=VideoTag.__table__, back_populates="tags")

    def __repr__(self) -> str:
        return f"<Tag {self.name}>"
