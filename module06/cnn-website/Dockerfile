# uv's own image: Python plus the uv binary, so there is no pip bootstrap step.
# Same base as module02/statusboard-uv, bumped to 3.13 to match requires-python.
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

# Dependencies first, in their own layer. pyproject.toml and uv.lock change far
# less often than the application code, so this install stays cached across
# edits to views.py.
COPY pyproject.toml uv.lock ./

# --frozen: install exactly what uv.lock pins and fail if it disagrees with
# pyproject.toml, rather than quietly resolving something new inside the image.
# --no-install-project: only the dependencies exist at this point.
RUN uv sync --frozen --no-install-project

# Now the code.
COPY . .

# Put the venv first on PATH so `alembic` and `flask` in compose.yaml's
# command resolve without spelling out /opt/venv/bin each time.
ENV PATH="/opt/venv/bin:$PATH"

EXPOSE 8000

# The default when compose does not override `command`. --host 0.0.0.0 so the
# published port can reach it; the default 127.0.0.1 would only be visible
# from inside the container.
CMD ["flask", "--app", "cnn_website", "run", "--host", "0.0.0.0", "--port", "8000"]
