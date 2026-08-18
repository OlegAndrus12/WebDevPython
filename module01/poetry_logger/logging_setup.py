"""Central logging configuration.

Call configure() once, from the process entry point (app.py). Library modules
only ever do `logging.getLogger(__name__)` — they never attach handlers of
their own, so importing checks.py from a test or a cron job never leaves a
stray handler behind.
"""

from __future__ import annotations

import logging
from pathlib import Path

LOG_FILE = Path(__file__).parent / "statusboard.log"


def configure(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if root.handlers:
        # Flask's debug reloader re-imports app.py in the same process; without
        # this guard every reload would double up the handlers, and every log
        # line would print twice.
        return

    root.setLevel(level)
    formatter = logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)
