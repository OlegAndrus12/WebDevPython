#!/bin/sh
# Start command for Render.
#
# Render does not run its Docker Command through a shell -- it splits the field
# into argv, substitutes variables and execs -- so `alembic ... && uvicorn ...`
# cannot be expressed there. This script is the one executable that does both.
#
#   Render -> Settings -> Docker Command:  sh render-start.sh
set -e

# A gate, not a nicety: `set -e` stops the container if the migration fails,
# rather than letting it serve against the wrong schema.
alembic upgrade head

# exec, so uvicorn replaces this shell as PID 1 and still receives SIGTERM when
# Render shuts the instance down. PORT is Render's; 8000 is the local default.
exec uvicorn news:app --host 0.0.0.0 --port "${PORT:-8000}"
