#!/usr/bin/env bash
# Restore a Mnemo snapshot directory into the current stack.
# Usage: ./scripts/restore.sh ./backups/2026-05-27T12-00-00Z
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DIR="${1:-}"
if [[ -z "$DIR" || ! -d "$DIR" ]]; then
    echo "Usage: $0 <backup-dir>" >&2
    exit 2
fi

# shellcheck disable=SC1091
set -a; . .env; set +a

echo "!! This will overwrite the live Postgres / Qdrant / MinIO state."
read -rp "Type 'YES' to continue: " confirm
[[ "$confirm" == "YES" ]] || { echo "Aborted."; exit 1; }

echo "→ Stopping services that hold connections"
docker compose stop api workers bot

echo "→ Postgres restore"
gunzip -c "$DIR/postgres.sql.gz" | docker compose exec -T postgres \
    psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"

echo "→ Qdrant restore"
docker compose exec -T qdrant rm -rf /qdrant/snapshots/mnemo_chunks
docker compose exec -T qdrant mkdir -p /qdrant/snapshots/mnemo_chunks
docker compose cp "$DIR/qdrant.snapshot" qdrant:/qdrant/snapshots/mnemo_chunks/
docker compose exec -T qdrant curl -fsS -X PUT \
    "http://localhost:6333/collections/mnemo_chunks/snapshots/recover" \
    -H 'Content-Type: application/json' \
    -d "{\"location\": \"file:///qdrant/snapshots/mnemo_chunks/$(basename "$DIR/qdrant.snapshot")\"}"

echo "→ MinIO restore (manual: copy $DIR/minio_bucket/ → minio:/data/)"
if [[ -d "$DIR/minio_bucket" ]]; then
    docker compose cp "$DIR/minio_bucket" "minio:/data/${MINIO_BUCKET:-mnemo-blobs}"
fi

echo "→ Restarting services"
docker compose start api workers bot
echo "Done."
