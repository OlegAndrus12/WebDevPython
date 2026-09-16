"""The article routes: listing, paging, searching, reading one, liking."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from news.models import LikedArticle


async def test_listing_needs_a_token(client, articles):
    await articles.create()

    response = await client.get("/api/articles")

    assert response.status_code == 401


async def test_listing_returns_newest_first(client, auth_headers, articles):
    """`create_many` spaces its articles an hour apart, so "newest" is a fact
    and not a coincidence of insertion order."""
    made = await articles.create_many(3)

    response = await client.get("/api/articles", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert [a["id"] for a in body["articles"]] == [a.id for a in made]


@pytest.mark.parametrize(
    ("page", "expected"),
    [
        pytest.param(1, slice(0, 2), id="first-page"),
        pytest.param(3, slice(4, 5), id="last-page-is-short"),
        pytest.param(4, slice(5, 5), id="past-the-end-is-empty-not-404"),
    ],
)
async def test_paging(client, auth_headers, articles, page, expected):
    """Five articles, two per page."""
    made = await articles.create_many(5)

    response = await client.get(
        "/api/articles", params={"page": page, "per_page": 2}, headers=auth_headers
    )

    body = response.json()
    assert [a["id"] for a in body["articles"]] == [a.id for a in made[expected]]
    assert body["pages"] == 3


@pytest.mark.parametrize(
    ("query", "expected_titles"),
    [
        pytest.param("election", ["The election result"], id="matches-a-title"),
        pytest.param("ELECTION", ["The election result"], id="is-case-insensitive"),
        pytest.param("rainfall", ["Weather today"], id="matches-the-description-too"),
        pytest.param("penguins", [], id="matches-nothing"),
        # What utils.like_escape exists for: unescaped, this query becomes
        # LIKE '%%%' and returns the whole table.
        pytest.param("%", ["100% certain"], id="a-percent-is-a-character"),
    ],
)
async def test_search(client, auth_headers, articles, query, expected_titles):
    """`q` is an ILIKE over title and description."""
    await articles.create(title="The election result", description="Who won.")
    await articles.create(title="Weather today", description="Heavy rainfall expected.")
    await articles.create(title="100% certain", description="No doubt.")

    response = await client.get("/api/articles", params={"q": query}, headers=auth_headers)

    assert [a["title"] for a in response.json()["articles"]] == expected_titles


async def test_reading_a_missing_article_is_404(client, auth_headers):
    response = await client.get("/api/articles/999", headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "article not found"


async def test_the_second_read_comes_from_the_cache(
    client, auth_headers, articles, session, fake_redis
):
    """Proved by changing the row underneath the cache and still getting the old
    title back. Stale is the correct answer here."""
    article = await articles.create(title="First headline")
    await client.get(f"/api/articles/{article.id}", headers=auth_headers)
    assert f"article:{article.id}" in fake_redis.store

    article.title = "Second headline"
    await session.flush()

    response = await client.get(f"/api/articles/{article.id}", headers=auth_headers)
    assert response.json()["title"] == "First headline"

    # Rules out the change simply not having been saved.
    fake_redis.store.clear()
    response = await client.get(f"/api/articles/{article.id}", headers=auth_headers)
    assert response.json()["title"] == "Second headline"


async def test_like_unlike_round_trip(client, auth_headers, articles, session):
    """The second like is the point: a duplicate insert on the composite primary
    key would reach the client as a 500, and a double-click is not an error."""
    article = await articles.create(title="Worth keeping")

    assert (await client.post(f"/api/articles/{article.id}/like", headers=auth_headers)).status_code == 204
    assert (await client.post(f"/api/articles/{article.id}/like", headers=auth_headers)).status_code == 204
    assert await session.scalar(select(func.count()).select_from(LikedArticle)) == 1

    response = await client.get("/api/me/liked", headers=auth_headers)
    assert [a["title"] for a in response.json()] == ["Worth keeping"]

    await client.delete(f"/api/articles/{article.id}/like", headers=auth_headers)
    assert (await client.get("/api/me/liked", headers=auth_headers)).json() == []


async def test_likes_are_per_user(client, auth_headers, users, articles):
    """Catches a query that forgot its `WHERE user_id =`, which passes every
    single-user test in this file."""
    article = await articles.create()
    somebody_else = await users.create()
    await articles.like(somebody_else, article)

    response = await client.get("/api/me/liked", headers=auth_headers)

    assert response.json() == []
