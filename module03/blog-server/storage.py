"""Reading and writing the feed — everything lives in one JSON file."""

import json

from utils import BASE_DIR

DATA_FILE = BASE_DIR / "data" / "posts.json"


def load_posts():
    """Return the stored posts, or an empty feed if the file is missing/broken."""
    if not DATA_FILE.exists():
        return []
    try:
        with DATA_FILE.open(encoding="utf-8") as f:
            posts = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[warn] could not read {DATA_FILE}: {e} — starting from an empty feed")
        return []

    return posts if isinstance(posts, list) else []


def save_posts(posts):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(posts, f, indent=2, ensure_ascii=False)


def find_post(posts, post_id):
    for post in posts:
        if post["id"] == post_id:
            return post
    return None
