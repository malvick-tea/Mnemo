#!/usr/bin/env bash
# Sign a JSON file with the webhook HMAC secret. For local workflow testing.
# Usage: ./scripts/hmac_sign.sh body.json
set -euo pipefail
F="${1:?usage: hmac_sign.sh <file>}"
SECRET="${MNEMO_WEBHOOK_HMAC_SECRET:-$(grep -E '^MNEMO_WEBHOOK_HMAC_SECRET=' .env | cut -d= -f2-)}"
TS=$(date +%s)
SIG=$(printf '%s.' "$TS" | cat - "$F" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $2}')
printf 'X-Mnemo-Timestamp: %s\nX-Mnemo-Signature: %s\n' "$TS" "$SIG"
