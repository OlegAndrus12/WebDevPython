FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

# The venv lives OUTSIDE /app, which is the whole trick. docker-compose.yaml
# bind-mounts the source over /app, and a venv at the default /app/.venv would
# be shadowed by the host's -- built for the host's interpreter, absolute
# shebangs and all. Putting it at /opt/venv means the bind mount cannot reach
# it, so no anonymous-volume hole is needed to protect it.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
# A cache that a named volume can persist, so the `uv sync` on container start
# (see the compose command) is a no-op rather than a re-download.
ENV UV_CACHE_DIR=/opt/uv-cache

# Dependencies first, in their own layer: pyproject.toml and uv.lock change far
# less often than the application code.
COPY pyproject.toml uv.lock ./
# --no-install-project: this pyproject has no [build-system], so there is
# nothing to build -- `news` is imported from the working directory instead.
RUN uv sync --frozen --no-install-project

COPY . .

# The venv first on PATH, so `alembic` and `uvicorn` resolve without a prefix.
ENV PATH="/opt/venv/bin:$PATH"

EXPOSE 8000

# --host 0.0.0.0: the default 127.0.0.1 is the container's own loopback and the
# published port would never reach it.
CMD ["uvicorn", "news:app", "--host", "0.0.0.0", "--port", "8000"]
