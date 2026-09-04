FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

# Dependencies first, in their own layer: pyproject.toml and uv.lock change far
# less often than the application code.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY . .

# The venv first on PATH, so `alembic` and `uvicorn` resolve without a prefix.
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# --host 0.0.0.0: the default 127.0.0.1 is the container's own loopback and the
# published port would never reach it.
CMD ["uvicorn", "news:app", "--host", "0.0.0.0", "--port", "8000"]
