"""Package entry point.

    uv run flask --app cnn_website run --debug
    gunicorn cnn_website:app

The app object lives in views.py, next to the routes it carries. This module
re-exports it so `--app cnn_website` and `cnn_website:app` both resolve without
naming the submodule.

There is no `create_app()` factory any more. What a factory buys you is the
ability to build a second app with different config -- a test app pointed at
another database, most usefully. With one module-level `app` that is gone, so
tests configure through the environment (`DB_NAME=cnn_test`) instead, the same
way `flask run` and Compose already do.
"""

from .views import app

__all__ = ["app"]
