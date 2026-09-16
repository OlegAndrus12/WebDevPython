"""The JWT flow through the real routes: register -> verify -> login -> use."""

from __future__ import annotations

import pytest

from news.security import auth_service

from .conftest import DEFAULT_PASSWORD

REGISTRATION = {
    "username": "grace",
    "email": "grace@readers.example",
    "password": DEFAULT_PASSWORD,
}


def login_form(email: str, password: str = DEFAULT_PASSWORD) -> dict:
    """The field is `username` even though it holds an email -- that is
    OAuth2PasswordRequestForm's fixed shape, not a choice this app made."""
    return {"username": email, "password": password}


async def test_register_verify_login(client, outbox):
    """The whole happy path in one test: the sequence is the behaviour."""
    # 1. register. The account exists but cannot do anything yet.
    response = await client.post("/api/auth/register", json=REGISTRATION)
    assert response.status_code == 201

    assert response.json()["confirmed"] is False
    # 2. the verification email went out. Sent from a BackgroundTask, which
    #    Starlette still runs inside the ASGI call.
    assert len(outbox) == 1
    email = outbox[0]
    assert email.recipients == ["grace@readers.example"]

    # 3. login is refused, and says why -- not "invalid password".
    response = await client.post("/api/auth/login", data=login_form("grace@readers.example"))
    assert response.status_code == 401
    assert response.json()["detail"] == "Email is not verified"

    # 4. click the link, using the token out of the email the app really built.
    token = email.body["token"]
    response = await client.get(f"/api/auth/confirmed_email/{token}")
    assert response.json()["message"] == "Email confirmed"

    # 5. the same link again: a mail client that prefetches must not break it.
    response = await client.get(f"/api/auth/confirmed_email/{token}")
    assert response.json()["message"] == "Your email is already confirmed"

    # 6. now login works, and hands back a bearer token.
    response = await client.post("/api/auth/login", data=login_form("grace@readers.example"))
    assert response.status_code == 200

    # 7. and the token opens a protected route.
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    response = await client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["email"] == "grace@readers.example"


@pytest.mark.parametrize(
    ("field", "value", "detail"),
    [
        pytest.param("email", "taken@readers.example", "Email already registered", id="email"),
        pytest.param("username", "taken", "Username already taken", id="username"),
    ],
)
async def test_register_rejects_a_duplicate(client, users, field, value, detail):
    await users.create(username="taken", email="taken@readers.example")

    response = await client.post("/api/auth/register", json={**REGISTRATION, field: value})

    assert response.status_code == 409
    assert response.json()["detail"] == detail


@pytest.mark.parametrize(
    "header",
    [
        pytest.param(None, id="no-header-at-all"),
        pytest.param({"Authorization": "Bearer garbage"}, id="not-a-jwt"),
        # Correctly signed, for the wrong purpose: a link mailed to an inbox is
        # weaker than a password and must not work as one.
        pytest.param("verification-token", id="right-signature-wrong-scope"),
    ],
)
async def test_me_refuses_an_unusable_token(client, reader, header):
    if header == "verification-token":
        token = await auth_service.create_verification_token(reader.email)
        header = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/auth/me", headers=header)

    assert response.status_code == 401


async def test_stats_is_closed_to_ordinary_readers(client, auth_headers):
    """403 and not 401: "not you", rather than "who are you"."""
    response = await client.get("/api/stats", headers=auth_headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "Admins only"


async def test_stats_is_open_to_admins(client, admin_headers, articles):
    """The same route, one column different on the user row."""
    await articles.create_many(3, source_slug="cnn")
    await articles.create(source_slug="bbc-news")

    response = await client.get("/api/stats", headers=admin_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total_articles"] == 4
    # Ordered by count, descending -- see Repository.article_counts_by_source.
    assert [source["slug"] for source in body["sources"]] == ["cnn", "bbc-news"]
