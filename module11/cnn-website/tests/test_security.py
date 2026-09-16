"""AuthService on its own: no database, no HTTP."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from jose import jwt

from news.security import AuthService, auth_service
from news.settings import settings

SECRET = settings.secret_key.get_secret_value()


def decode(token: str) -> dict:
    """Decode without AuthService, so the encoder is not checked against itself."""
    return jwt.decode(token, SECRET, algorithms=[AuthService.ALGORITHM])


async def test_hashing_is_salted_and_still_verifies():
    """Two hashes of one password differ, and both verify."""
    first = await auth_service.hash_password("hunter2")
    second = await auth_service.hash_password("hunter2")

    assert first != second
    assert await auth_service.verify_password("hunter2", first)
    assert await auth_service.verify_password("hunter2", second)


@pytest.mark.parametrize(
    ("factory", "expected_scope"),
    [
        (auth_service.create_access_token, "access_token"),
        (auth_service.create_verification_token, "verification_token"),
    ],
)
async def test_tokens_carry_subject_and_scope(factory, expected_scope):
    """Both token kinds are the same three claims; only `scope` differs."""
    payload = decode(await factory("grace@readers.example"))

    assert payload["sub"] == "grace@readers.example"
    assert payload["scope"] == expected_scope
    assert payload["exp"] > datetime.now(timezone.utc).timestamp()


async def test_an_access_token_is_not_a_verification_token():
    """Without the scope check, a token held all day would confirm any address."""
    access = await auth_service.create_access_token("grace@readers.example")

    with pytest.raises(HTTPException) as exc_info:
        await auth_service.decode_verification_token(access)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid scope for token"


@pytest.mark.parametrize(
    "token",
    [
        pytest.param("obviously-not-a-token", id="not-a-jwt"),
        # Backdated rather than waited out: python-jose checks `exp` against
        # the real clock, so signing one in the past is the cheapest way in.
        pytest.param(
            jwt.encode(
                {
                    "sub": "a@readers.example",
                    "scope": "verification_token",
                    "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
                },
                SECRET,
            ),
            id="expired",
        ),
    ],
)
async def test_unusable_verification_tokens_are_refused(token):
    with pytest.raises(HTTPException) as exc_info:
        await auth_service.decode_verification_token(token)

    assert exc_info.value.status_code == 422
