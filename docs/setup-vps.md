# Mnemo on a fresh Ubuntu 24.04 VPS

Tested on a $5/mo Hetzner / DigitalOcean droplet. 2 GB RAM is the practical
floor; 4 GB is comfortable if you'll embed locally with Ollama.

## 1. Server prep

```bash
# As root
apt update && apt -y upgrade
apt -y install ufw curl ca-certificates

ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# Non-root user
adduser --disabled-password --gecos "" mnemo
usermod -aG sudo mnemo
mkdir -p /home/mnemo/.ssh
cp ~/.ssh/authorized_keys /home/mnemo/.ssh/
chown -R mnemo:mnemo /home/mnemo/.ssh
```

Log back in as `mnemo`.

## 2. Docker

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker         # apply the group without re-login
docker run --rm hello-world
```

## 3. DNS

Point an A record (e.g. `mnemo.example.com`) at your VPS IP. Wait for it to
resolve before continuing — Caddy will fail TLS provisioning otherwise.

```bash
dig +short mnemo.example.com   # should show your VPS IP
```

## 4. Clone & bootstrap

```bash
git clone https://github.com/yourname/mnemo.git
cd mnemo
./scripts/bootstrap.sh
```

The script will ask for:
- **Telegram bot token** — get from [@BotFather](https://t.me/BotFather).
- **Your TG numeric user ID** — message [@userinfobot](https://t.me/userinfobot).
- **Domain** — the FQDN from step 3.
- **LLM provider** — pick `openrouter` for the default cloud setup.
- **OpenRouter key** — only if you chose openrouter.

It then generates all secrets, runs `docker compose up -d`, waits for the
API to report ready, and imports the n8n workflows. Should finish in 2-4
minutes.

## 5. Sanity check

1. Message your bot. Send `/start`.
2. Send any text. You should see "📝 Saving…" → "✅ Saved." within ~2 s.
3. Send `/q test`. Even without prior captures, the bot should reply.
4. (Optional) `make logs` and confirm structured JSON logs flowing.

## 6. Updates

```bash
cd ~/mnemo
git pull
docker compose pull
docker compose up -d
docker compose exec api alembic upgrade head
```

See [docs/upgrades.md](upgrades.md) for breaking-change notes.

## 7. Backups

The default `scripts/backup.sh` writes to `./backups/<UTC-stamp>/`. Wire it
into cron:

```bash
crontab -e
# At 04:17 UTC every day:
17 4 * * * cd /home/mnemo/mnemo && ./scripts/backup.sh >> ./backups/backup.log 2>&1
```

Off-host the backups (rclone, restic, your provider's snapshot, etc.). The
worst-case scenario for a self-host is "VPS gone, no backup".

## 8. Troubleshooting

| Symptom | Likely cause |
|---|---|
| Bot replies "Reference: abcd…" with no work done | API down — `make logs api` |
| "🚧 Slow down…" reply on every message | Throttle bucket; tune `MNEMO_THROTTLE_PER_MIN` |
| Caddy can't get a cert | DNS hasn't propagated; check `dig` |
| 401 on n8n webhooks | `MNEMO_WEBHOOK_HMAC_SECRET` mismatch between n8n and API containers |
| Bot ignores your messages | You're not in `MNEMO_ALLOWED_TG_IDS` |
