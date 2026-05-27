#!/usr/bin/env bash
# Mnemo first-run setup. Interactive; idempotent.
# Goal: clone → ./scripts/bootstrap.sh → working bot in < 5 minutes.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
warn() { printf '\033[33m! %s\033[0m\n' "$*"; }
ok()   { printf '\033[32m✓ %s\033[0m\n' "$*"; }

need() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "Required command not found: $1" >&2
        exit 1
    fi
}

need docker
need openssl
docker compose version >/dev/null 2>&1 || {
    echo "Need 'docker compose' (v2 plugin)" >&2
    exit 1
}

bold "Mnemo bootstrap"
echo "We'll write a .env file and start the stack."
echo "Re-run anytime — existing values in .env are kept."
echo

if [[ -f .env ]]; then
    bold "Found existing .env. Loading."
    set -a
    # shellcheck disable=SC1091
    . .env
    set +a
else
    cp .env.example .env
fi

prompt() {
    local var="$1" label="$2" default="${3:-}"
    local current="${!var:-}"
    if [[ -n "$current" && "$current" != "CHANGEME"* && "$current" != "" ]]; then
        return
    fi
    if [[ -n "$default" ]]; then
        read -rp "$label [$default]: " val
        val="${val:-$default}"
    else
        read -rp "$label: " val
    fi
    sed -i.bak -E "s|^${var}=.*|${var}=${val}|" .env && rm -f .env.bak
    export "$var"="$val"
}

prompt TELEGRAM_BOT_TOKEN "Telegram bot token (from @BotFather)"
prompt MNEMO_ALLOWED_TG_IDS "Comma-separated TG user IDs allowed to use the bot"
prompt MNEMO_DOMAIN "Public domain for HTTPS (or 'localhost' for local dev)" "localhost"
prompt MNEMO_LLM_PROVIDER "LLM provider [openrouter|ollama]" "openrouter"

if [[ "${MNEMO_LLM_PROVIDER:-}" == "openrouter" ]]; then
    prompt OPENROUTER_API_KEY "OpenRouter API key (https://openrouter.ai)"
fi

# ── Generate secrets if still default ─────────────────────────────────────────
gen_secret_64() { openssl rand -hex 32; }
gen_secret_b64_32() { openssl rand -base64 32; }

substitute() {
    local key="$1" value="$2"
    sed -i.bak -E "s|^${key}=.*|${key}=${value}|" .env && rm -f .env.bak
}

ensure_secret() {
    local key="$1" generator="$2"
    local current
    current="$(grep -E "^${key}=" .env | cut -d= -f2-)"
    if [[ -z "$current" || "$current" == "CHANGEME"* ]]; then
        substitute "$key" "$($generator)"
        ok "Generated $key"
    fi
}

ensure_secret MNEMO_SERVICE_JWT_SECRET gen_secret_64
ensure_secret MNEMO_WEBHOOK_HMAC_SECRET gen_secret_64
ensure_secret MNEMO_ENCRYPTION_KEY gen_secret_b64_32
ensure_secret POSTGRES_PASSWORD gen_secret_64
ensure_secret MINIO_SECRET_KEY gen_secret_64
ensure_secret N8N_BASIC_AUTH_PASSWORD gen_secret_64
ensure_secret N8N_ENCRYPTION_KEY gen_secret_64

if [[ -z "${TELEGRAM_WEBHOOK_PATH:-}" || "${TELEGRAM_WEBHOOK_PATH}" == "/telegram/CHANGEME" ]]; then
    substitute TELEGRAM_WEBHOOK_PATH "/telegram/$(openssl rand -hex 8)"
    ok "Generated TELEGRAM_WEBHOOK_PATH"
fi

# Caddyfile (replace placeholder)
if [[ ! -f Caddyfile ]]; then
    cp Caddyfile.example Caddyfile
    ok "Created Caddyfile from example"
fi

# n8n Basic Auth — Caddy expects a bcrypt hash. We compute it via `caddy hash-password`.
if [[ -z "${N8N_BASIC_AUTH_PASSWORD_HASH:-}" ]]; then
    HASH="$(docker run --rm caddy:2.8-alpine caddy hash-password --plaintext "$(grep -E '^N8N_BASIC_AUTH_PASSWORD=' .env | cut -d= -f2-)" 2>/dev/null || true)"
    if [[ -n "$HASH" ]]; then
        if grep -q '^N8N_BASIC_AUTH_PASSWORD_HASH=' .env; then
            substitute N8N_BASIC_AUTH_PASSWORD_HASH "${HASH//|/\\|}"
        else
            printf '\nN8N_BASIC_AUTH_PASSWORD_HASH=%s\n' "$HASH" >> .env
        fi
        ok "Hashed N8N_BASIC_AUTH_PASSWORD for Caddy"
    else
        warn "Could not hash N8N password — fill N8N_BASIC_AUTH_PASSWORD_HASH manually."
    fi
fi

bold "Pulling images and starting stack…"
docker compose pull
docker compose up -d

bold "Waiting for API to report ready (up to 90 s)…"
for i in $(seq 1 30); do
    if docker compose exec -T api wget -qO- http://localhost:8000/v1/readyz >/dev/null 2>&1; then
        ok "API is ready."
        break
    fi
    sleep 3
done

bold "Importing n8n workflows…"
./scripts/n8n_import.sh || warn "n8n import failed; you can rerun via 'make n8n-import'."

ok "Done."
echo
echo "Send a message to your bot now."
[[ "${MNEMO_DOMAIN:-}" != "localhost" ]] && echo "n8n UI: https://${MNEMO_DOMAIN}/n8n/"
echo "Tail logs: make logs"
