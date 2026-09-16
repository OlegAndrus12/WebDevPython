"""Load test for GET /api/articles.

    uv sync --group e2e --group load
    DEBUG=false docker compose up -d --wait
    LOAD_EMAIL=you@example.com LOAD_PASSWORD=... \
        uv run locust -f tests/load/locustfile.py --headless -u 50 -r 10 -t 30s

Needs a confirmed user and some articles already in the database. See
README.md for the settings that have to be off and why.
"""

from __future__ import annotations

import os
import random

import requests
from locust import HttpUser, between, events, task

BASE_URL = os.environ.get("LOAD_BASE_URL", "http://localhost:8011").rstrip("/")
LOGIN = {
    "username": os.environ.get("LOAD_EMAIL", ""),
    "password": os.environ.get("LOAD_PASSWORD", ""),
}

token = ""


@events.test_start.add_listener
def set_up(**_kwargs) -> None:
    global token

    try:
        probe = [requests.get(f"{BASE_URL}/api/auth/me").status_code for _ in range(2)]
    except requests.RequestException as exc:
        raise SystemExit(f"no app at {BASE_URL} ({exc}) -- `docker compose up -d --wait`")

    login = requests.post(f"{BASE_URL}/api/auth/login", data=LOGIN, timeout=30)
    if login.status_code != 200:
        raise SystemExit(f"login failed: {login.status_code} {login.text}")
    token = login.json()["access_token"]

    listing = requests.get(
        f"{BASE_URL}/api/articles", headers={"Authorization": f"Bearer {token}"}
    )
    if not listing.json()["total"]:
        raise SystemExit("no articles in the database -- open http://localhost:8011/ once")


class Reader(HttpUser):
    host = BASE_URL
    wait_time = between(0.5, 2.0)

    def on_start(self) -> None:
        self.client.headers["Authorization"] = f"Bearer {token}"

    @task
    def browse_the_list(self) -> None:
        self.client.get("/api/articles", params={"page": random.randint(1, 3)})
