#!/usr/bin/env bash
# Import every JSON in n8n/workflows/ into the running n8n container.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# `docker compose ps -q n8n` prints the container ID when the service is
# running, empty otherwise. Plain `ps --quiet` would always return 0
# (the command succeeded) even if n8n is down.
container_id="$(docker compose ps -q n8n 2>/dev/null || true)"
if [[ -z "$container_id" ]]; then
    echo "n8n container is not running. Start it first (e.g. 'make dev' or 'docker compose up -d n8n')." >&2
    exit 1
fi

shopt -s nullglob
files=(n8n/workflows/*.json)
if (( ${#files[@]} == 0 )); then
    echo "No workflows found in n8n/workflows/." >&2
    exit 0
fi

failures=0
for f in "${files[@]}"; do
    name="$(basename "$f")"
    echo "→ importing $name"
    if ! docker compose exec -T n8n n8n import:workflow --input "/workflows/$name"; then
        echo "  (failed; continuing)" >&2
        failures=$((failures + 1))
    fi
done

if (( failures > 0 )); then
    echo "Done with $failures failure(s)." >&2
    exit 1
fi
echo "Done."
