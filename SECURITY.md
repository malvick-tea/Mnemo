# Security

## Threat model (v1)

**Adversaries we design against:**
- Opportunistic internet scanners hitting our public surface (Caddy, Telegram
  bot, n8n UI behind basic auth).
- A malicious or compromised dependency in our Python supply chain.
- A user mis-configuring a public-facing instance.

**Adversaries we explicitly do *not* design against** (v1):
- Nation-state actors.
- A motivated attacker with physical access to the VPS.
- Insider threats (single-user product; you are the insider).

## What's actually exposed to the internet

Only **Caddy** binds to `:80` / `:443`. Everything else (`api`, `bot`,
`postgres`, `qdrant`, `redis`, `minio`, `n8n`, `workers`) sits on an internal
docker network unreachable from outside.

Caddy proxies:

| route | target | auth |
|---|---|---|
| `POST /telegram/<bot_token_path>` | bot | shared-secret in URL path |
| `/n8n/*` | n8n UI | HTTP Basic Auth (set in `.env`) |
| `/admin/*` | webapp | HTTP Basic Auth (re-uses the n8n creds in v1) |

The Core API is **not** exposed publicly. Bot and webapp talk to it over the
internal network with a service JWT.

## Authentication

- **Telegram users:** whitelist in `MNEMO_ALLOWED_TG_IDS`. The bot rejects
  every update from a TG user not on the list — no `/start`, no `/help`,
  nothing leaks. The whitelist is the *only* gate; this is a single-user
  product by design in v1.
- **Service-to-service:** bot → API uses a service JWT signed with
  `MNEMO_SERVICE_JWT_SECRET`. Short-lived (15 min), rotated on every request.
- **Webhooks (API ↔ n8n):** HMAC-SHA256 over the body using
  `MNEMO_WEBHOOK_HMAC_SECRET`. Replay protection via the `idempotency_keys`
  table (5-minute timestamp window).

## Secrets

- `.env` is never committed. `.env.example` documents every variable.
- Integration credentials (Notion API keys, etc.) at rest in Postgres are
  encrypted with AES-GCM. The key lives in `MNEMO_ENCRYPTION_KEY` (32 bytes,
  base64). `scripts/bootstrap.sh` generates one if missing.
- Bot token, API keys, JWT secrets — all in `.env`, loaded by Pydantic
  Settings at boot. The app refuses to start if any required secret is empty
  or obviously default ("changeme", etc.).

## PII in logs

The default log level redacts user message bodies and shows only correlation
IDs. Set `MNEMO_LOG_PII=true` (off by default) to include bodies when
debugging — and remember to turn it off.

## Backups

`scripts/backup.sh` dumps Postgres (`pg_dump`), snapshots Qdrant via its API,
and mirrors the MinIO bucket. Output: `./backups/<UTC-timestamp>/`.
`scripts/restore.sh` does the reverse. Both are non-interactive and safe to
run from cron.

## Reporting a vulnerability

Email **security@example.com** (replace before publishing your fork). Include:

- Affected commit / version
- Reproduction steps
- Impact assessment
- Any PoC

We will acknowledge within 72 hours and aim to ship a fix or mitigation
within 14 days for high-severity issues. We do not currently run a bug
bounty program.

Please do **not** open a public GitHub issue for security reports.

## Known limitations

- **Single-tenant by design.** Hosting Mnemo for multiple distrusting users
  is unsupported in v1. The whitelist is the only authorization boundary.
- **No automatic rotation** of the AES-GCM encryption key. If you suspect
  `MNEMO_ENCRYPTION_KEY` was compromised, follow the rotation steps in
  `docs/upgrades.md`.
- **n8n UI on the same domain.** Behind HTTP Basic Auth, but a strong
  unique password is your responsibility. Consider IP-allowlisting it in
  Caddy if your VPS provider supports it.
