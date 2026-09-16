"""Response models. What FastAPI serialises, and what /docs documents."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .models import Role


class SourceOut(BaseModel):
    """The outlet an article came from, as NewsAPI names it."""

    model_config = ConfigDict(from_attributes=True)

    slug: str = Field(
        description="Stable NewsAPI identifier, safe to use as a filter value.",
        examples=["cnn"],
    )
    name: str = Field(description="Display name.", examples=["CNN"])


class ArticleOut(BaseModel):
    """One stored article. Every field but `id`, `title` and `url` may be null:
    NewsAPI omits them freely and we store what we are given."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Primary key, and the id in the item routes.", examples=[42])
    title: str = Field(examples=["Markets close higher after rate decision"])
    description: str | None = Field(
        default=None,
        description="Short teaser. Null when the source published none.",
        examples=["Indices recovered late in the session."],
    )
    content: str | None = Field(
        default=None,
        description="Truncated body text -- NewsAPI cuts it at ~200 characters.",
        examples=["Stocks rallied into the close as traders... [+1893 chars]"],
    )
    url: str = Field(
        description="Canonical link on the publisher's own site.",
        examples=["https://www.cnn.com/2026/09/15/markets/rate-decision"],
    )
    image_url: str | None = Field(
        default=None,
        description="Lead image, already absolute.",
        examples=["https://media.cnn.com/api/v1/images/stellar/prod/lead.jpg"],
    )
    author: str | None = Field(default=None, examples=["Jane Doe"])
    published_at: datetime | None = Field(
        default=None,
        description="Publication time in UTC, as reported by the source.",
        examples=["2026-09-15T08:30:00Z"],
    )
    source: SourceOut


class ArticlePage(BaseModel):
    """One page of results plus the paging state that produced it, so a client
    can render controls without echoing back its own request."""

    articles: list[ArticleOut] = Field(
        description="This page only, newest first. Empty past the last page."
    )
    query: str = Field(
        description="The search term after trimming; empty string when unfiltered.",
        examples=["markets"],
    )
    page: int = Field(description="1-based index of this page.", examples=[1])
    per_page: int = Field(description="Page size that was applied.", examples=[20])
    total: int = Field(
        description="Articles matching `query` across all pages.", examples=[137]
    )
    pages: int = Field(
        description="Total page count for `total` at this `per_page`.", examples=[7]
    )


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
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    confirmed: bool
    subscribed: bool
    role: Role


class SubscriptionIn(BaseModel):
    """Body of PUT /api/me/subscription -- the state to move to, not a toggle."""

    subscribed: bool


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RequestEmail(BaseModel):
    """Body of POST /api/auth/request_email -- resend the verification link."""

    email: EmailStr


class Message(BaseModel):
    """A bare human-readable result, for the endpoints that have nothing else"""

    message: str
