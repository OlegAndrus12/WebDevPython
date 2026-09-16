"""The rate limiter, which conftest.py switches off for every other test."""


async def test_a_second_request_inside_the_window_is_refused(
    client, auth_headers, rate_limiter_on
):
    """A cooldown, not a quota. `Retry-After` is what makes a client back off."""
    first = await client.get("/api/articles", headers=auth_headers)
    second = await client.get("/api/articles", headers=auth_headers)

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers["retry-after"] == "1"
