
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SERVICES_FILE = Path(__file__).parent / "services.json"


def load() -> dict[str, str]:
    """Read the watch list. A missing file means an empty board, not a crash."""
    if not SERVICES_FILE.exists():
        logger.debug("%s does not exist yet; returning an empty watch list", SERVICES_FILE)
        return {}
    return json.loads(SERVICES_FILE.read_text(encoding="utf-8"))


def save(services: dict[str, str]) -> None:
    SERVICES_FILE.write_text(
        json.dumps(services, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    logger.debug("Wrote %d service(s) to %s", len(services), SERVICES_FILE)


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
