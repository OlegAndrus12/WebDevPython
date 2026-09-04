"""Package entry point.

    uv run uvicorn news:app --reload
    uvicorn news:app --host 0.0.0.0 --port 8000

The app object lives in main.py; this re-export is what lets the import string
stay `news:app`.
"""

from .main import app

__all__ = ["app"]
