#!/bin/sh
# Production entrypoint.
# - Apply outstanding DB migrations (idempotent — Alembic no-ops if already at head).
# - Then exec whatever CMD follows (gunicorn for the api, arq for the worker).
#
# `alembic upgrade head` blocks the start of the app until migrations finish.
# That's the right behavior on Render/Railway — they restart the container
# until it stays healthy, so a slow migration just delays cutover.
#
# Multiple replicas starting at once is safe: Alembic uses a row lock on the
# `alembic_version` table.

set -e

if [ "${SKIP_MIGRATIONS:-0}" != "1" ]; then
  echo "[entrypoint] Running alembic upgrade head ..."
  alembic upgrade head
else
  echo "[entrypoint] SKIP_MIGRATIONS=1 — skipping migrations"
fi

echo "[entrypoint] Starting: $*"
exec "$@"
