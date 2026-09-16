"""Register, verify, log in, like, and read the likes back -- in a real browser.

Nothing in the unit suite ever runs auth.js, so a token stored under the wrong
localStorage key, a fetch that forgets the Authorization header or a template
rendering the wrong data-article-id would leave it green and the site unusable.

    uv run pytest -m e2e --no-cov                                # ~8s, headless
    E2E_SLOWMO=1 uv run pytest -m e2e --no-cov -k browser_flow   # watch it, ~30s
"""

from __future__ import annotations

import httpx
import pytest
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .conftest import BASE_URL, PASSWORD, TIMEOUT_SECONDS, verification_link

# Keeps the module out of a bare `uv run pytest` -- see pyproject.toml's addopts.
pytestmark = pytest.mark.e2e

TOKEN_KEY = "cnn_token"  # auth.js's localStorage key


# --- small helpers over Selenium -------------------------------------------


def wait(driver) -> WebDriverWait:
    return WebDriverWait(driver, TIMEOUT_SECONDS)


def fill(driver, field_id: str, value: str) -> None:
    element = wait(driver).until(EC.element_to_be_clickable((By.ID, field_id)))
    element.clear()
    element.send_keys(value)


def submit(driver, form_id: str) -> None:
    driver.find_element(By.CSS_SELECTOR, f"#{form_id} button[type=submit]").click()


def visible_error(driver) -> str:
    """`#auth-error`'s text, or "" while hidden. Every wait below checks it too,
    so a failure reports "Email is not verified" rather than a bare timeout."""
    found = driver.find_elements(By.ID, "auth-error")
    if found and found[0].is_displayed():
        return found[0].text
    return ""


def browser_token(driver) -> str | None:
    """Guarded: reading storage during a navigation raises, and this is polled
    straight through the redirect the login triggers."""
    try:
        return driver.execute_script(f"return window.localStorage.getItem({TOKEN_KEY!r});")
    except Exception:
        return None


def liked_titles(driver) -> list[str]:
    """The titles on /liked, in the order the page lists them."""
    return [
        element.text
        for element in driver.find_elements(By.CSS_SELECTOR, "#liked-list .card-title a")
    ]


# --- the flow, end to end ---------------------------------------------------


def test_liked_articles_survive_the_whole_browser_flow(driver, new_user, articles):
    """Five steps in the order a person would do them, because the sequence is
    the behaviour: split up, four of them would spend their time redoing the
    steps before, and none would show that the token minted at step 3 is the
    one that makes step 5 answer."""

    # --- 1. register, through the form -------------------------------------
    driver.get(f"{BASE_URL}/register")
    fill(driver, "username", new_user["username"])
    fill(driver, "email", new_user["email"])
    fill(driver, "password", new_user["password"])
    submit(driver, "register-form")

    # Waiting on the message rather than the form's disappearance is the
    # stricter of the two: a missing #auth-success leaves showMessage with a
    # null element, and registering succeeds into a blank page.
    try:
        wait(driver).until(
            lambda d: d.find_element(By.ID, "auth-success").is_displayed() or visible_error(d)
        )
    except TimeoutException:  # pragma: no cover - only on a failure
        pytest.fail("register neither confirmed nor reported an error")

    assert not visible_error(driver), f"register failed: {visible_error(driver)}"
    assert new_user["email"] in driver.find_element(By.ID, "auth-success").text
    assert not driver.find_element(By.ID, "register-form").is_displayed()

    # --- 2. the verification email, read out of Mailpit --------------------
    #
    # The link the app really built, fetched from the inbox it really reached.
    link = verification_link(new_user["email"])
    assert link.startswith(BASE_URL), f"the email links somewhere else: {link}"

    driver.get(link)
    status = wait(driver).until(
        lambda d: (d.find_element(By.ID, "verify-status").text or "").strip() not in ("", "Confirming…")
        and d.find_element(By.ID, "verify-status")
    )
    assert status.text.strip() == "Email confirmed", status.text

    # --- 3. log in, and get a token --------------------------------------
    #
    # Before the click storage is empty; after it there is a JWT. That is the
    # whole of this app's session state.
    driver.get(f"{BASE_URL}/login")
    assert browser_token(driver) is None, "a token exists before anyone logged in"

    fill(driver, "email", new_user["email"])
    fill(driver, "password", new_user["password"])
    submit(driver, "login-form")

    try:
        wait(driver).until(lambda d: browser_token(d) or visible_error(d))
    except TimeoutException:  # pragma: no cover - only on a failure
        pytest.fail("login stored no token and showed no error")

    token = browser_token(driver)
    assert token, f"login failed: {visible_error(driver)}"
    # The shape, not the claims -- test_security.py owns those. This only needs
    # to know the browser got the token and not the JSON envelope.
    assert token.count(".") == 2, f"not a JWT: {token!r}"

    # --- 4. like two of the three articles ---------------------------------
    #
    # Through the ♥ on the article page: the button, its data-article-id and
    # the header auth.js attaches are what is untested anywhere else.
    liked = [articles[0], articles[2]]
    for article in liked:
        driver.get(f"{BASE_URL}/article/{article.id}")
        button = wait(driver).until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".like-btn")))
        assert button.get_attribute("aria-pressed") == "false"

        button.click()
        # The button fills in only after the POST returns 204, so waiting on it
        # is waiting on the write -- no sleep, no polling behind the app's back.
        wait(driver).until(
            lambda d: d.find_element(By.CSS_SELECTOR, ".like-btn").get_attribute("aria-pressed")
            == "true"
        )

    # --- 5. /liked lists them, and only them -------------------------------
    #
    # An empty shell filled from GET /api/me/liked with the token from step 3,
    # so asserting on the cards asserts the protected endpoint through the
    # client that actually calls it.
    driver.get(f"{BASE_URL}/liked")
    wait(driver).until(lambda d: len(liked_titles(d)) == len(liked))

    assert liked_titles(driver) == [
        liked[1].title,
        liked[0].title,
    ], "the page should list the newest like first"

    # A /me/liked that ignored its WHERE clause would pass everything above.
    assert articles[1].title not in liked_titles(driver)

    # --- and the endpoint itself, with the browser's own token -------------
    #
    # So a failure reads as "the API is wrong" or "the page is wrong", rather
    # than merely "something is wrong".
    response = httpx.get(
        f"{BASE_URL}/api/me/liked", headers={"Authorization": f"Bearer {token}"}, timeout=10
    )
    assert response.status_code == 200
    assert [article["id"] for article in response.json()] == [liked[1].id, liked[0].id]

    # 401, not an empty list -- an endpoint answering `[]` to a stranger would
    # have looked fine on every assertion above.
    assert httpx.get(f"{BASE_URL}/api/me/liked", timeout=10).status_code == 401


# --- the part of "for that user" that a single browser cannot show ----------


def test_one_readers_likes_are_invisible_to_another(make_confirmed_user, articles):
    """The test above proves the list is right; it cannot prove it is scoped,
    because it only ever has one user. Over HTTP, and with both accounts created
    already confirmed: registering two readers properly would cost two bcrypt
    hashes and two Mailpit round trips to set up what is not being tested."""
    reader, other = make_confirmed_user("a"), make_confirmed_user("b")

    def login(user) -> str:
        response = httpx.post(
            f"{BASE_URL}/api/auth/login",
            # Form-encoded, and the field is `username` though it holds an email.
            data={"username": user.email, "password": PASSWORD},
            timeout=10,
        )
        assert response.status_code == 200, response.text
        return response.json()["access_token"]

    def headers(user) -> dict[str, str]:
        return {"Authorization": f"Bearer {login(user)}"}

    reader_headers, other_headers = headers(reader), headers(other)

    like = httpx.post(
        f"{BASE_URL}/api/articles/{articles[0].id}/like", headers=reader_headers, timeout=10
    )
    assert like.status_code == 204

    mine = httpx.get(f"{BASE_URL}/api/me/liked", headers=reader_headers, timeout=10)
    assert [article["id"] for article in mine.json()] == [articles[0].id]

    theirs = httpx.get(f"{BASE_URL}/api/me/liked", headers=other_headers, timeout=10)
    assert theirs.json() == [], "another reader can see this user's likes"
