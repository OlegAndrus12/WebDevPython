"""Small helpers shared by the request handler and the storage layer."""

from pathlib import Path
import time

BASE_DIR = Path(__file__).parent


def now_ms():
    """Current time as integer milliseconds — what the frontend expects."""
    return int(time.time() * 1000)


def new_id(prefix="p"):
    return f"{prefix}{now_ms()}"


def clean(value, limit):
    """Trim a user-supplied string and cap its length."""
    return str(value or "").strip()[:limit]


def is_inside(target, root):
    """True when `target` resolves to a path under `root` (blocks ../ escapes)."""
    return target.resolve().is_relative_to(root.resolve())
