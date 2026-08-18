
from __future__ import annotations

import json
from pathlib import Path


SERVICES_FILE = Path(__file__).parent / "services.json"


def load() -> dict[str, str]:
    """Read the watch list. A missing file means an empty board, not a crash."""
    if not SERVICES_FILE.exists():
        return {}
    return json.loads(SERVICES_FILE.read_text(encoding="utf-8"))


def save(services: dict[str, str]) -> None:
    SERVICES_FILE.write_text(
        json.dumps(services, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def add(name: str, url: str) -> None:
    """Add one service. `url` may omit the scheme; https is assumed."""
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    services = load()
    services[name] = url
    save(services)


def remove(name: str) -> None:
    services = load()
    services.pop(name, None)
    save(services)
