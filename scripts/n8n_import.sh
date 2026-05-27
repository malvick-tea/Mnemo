#!/usr/bin/env bash
# Import every JSON in n8n/workflows/ into the running n8n container.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! docker compose ps n8n --quiet >/dev/null 2>&1; then
    echo "n8n container is not running. Start it first." >&2
    exit 1
fi

for f in n8n/workflows/*.json; do
    name=$(basename "$f")
    echo "→ importing $name"
    # n8n has a CLI for this:
    #   n8n import:workflow --input=<file>
    docker compose exec -T n8n n8n import:workflow --input "/workflows/$name" \
        || { echo "  (failed; continuing)"; continue; }
done
echo "Done."
