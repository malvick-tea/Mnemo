#!/usr/bin/env sh
# Container entrypoint for the Core API image.
#
# Applies database migrations *before* the application starts accepting
# traffic, then execs the given command (uvicorn). This guarantees the schema
# exists on every boot — `docker compose up` on an empty volume, a fresh
# bootstrap, or a redeploy after a new migration — instead of relying on a
# one-off manual step. `alembic upgrade head` is idempotent: it is a no-op
# when the database is already at head.
set -e

echo "[entrypoint] applying database migrations (alembic upgrade head)…"
alembic -c alembic.ini upgrade head
echo "[entrypoint] migrations applied; starting: $*"

exec "$@"
