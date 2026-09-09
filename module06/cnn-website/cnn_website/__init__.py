"""Package entry point: `flask --app cnn_website run`, or `cnn_website:app`.

The app object lives in views.py, next to the routes it carries; this re-export
is what lets the import string stay `cnn_website`.
"""

from .views import app

__all__ = ["app"]
