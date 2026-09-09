"""Response models: what FastAPI serialises, and what /docs documents."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class SourceOut(BaseModel):
    # from_attributes lets a route return the ORM object itself.
    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    content: str | None
    url: str
    image_url: str | None
    author: str | None
    published_at: datetime | None
    source: SourceOut


class ArticlePage(BaseModel):
    articles: list[ArticleOut]
    query: str
    page: int
    per_page: int
    total: int
    pages: int


class SourceCount(BaseModel):
    slug: str
    name: str
    articles: int


class Stats(BaseModel):
    sources: list[SourceCount]
    total_articles: int
    total_sources: int


class Health(BaseModel):
    status: str
    db: str


class UserCreate(BaseModel):
    username: str
    email: EmailStr


class UserUpdate(BaseModel):
    """Both optional: PATCH has to tell an omitted field from an explicit null,
    which is what `model_dump(exclude_unset=True)` in the route relies on.
    """

    username: str | None = None
    email: EmailStr | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
