#!/usr/bin/env bash
# Snapshot Postgres + Qdrant + MinIO into ./backups/<UTC>/
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

STAMP="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
OUT="$ROOT/backups/$STAMP"
mkdir -p "$OUT"

echo "→ Postgres dump"
docker compose exec -T postgres pg_dump -U "${POSTGRES_USER:-mnemo}" \
    --no-owner --no-privileges "${POSTGRES_DB:-mnemo}" \
    | gzip -9 > "$OUT/postgres.sql.gz"

echo "→ Qdrant snapshot"
SNAPSHOT_RESP=$(docker compose exec -T qdrant \
    curl -fsS -X POST "http://localhost:6333/collections/mnemo_chunks/snapshots")
SNAPSHOT_NAME=$(echo "$SNAPSHOT_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['name'])")
docker compose cp "qdrant:/qdrant/snapshots/mnemo_chunks/$SNAPSHOT_NAME" "$OUT/qdrant.snapshot"

echo "→ MinIO mirror"
docker compose exec -T minio mc alias set local http://localhost:9000 \
    "${MINIO_ACCESS_KEY:-mnemo}" "${MINIO_SECRET_KEY}" >/dev/null
docker compose cp "minio:/data/${MINIO_BUCKET:-mnemo-blobs}" "$OUT/minio_bucket" || true

echo "→ Done: $OUT"
du -sh "$OUT"
