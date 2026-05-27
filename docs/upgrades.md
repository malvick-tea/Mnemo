# Upgrades

Mnemo follows semver: `v1.X.Y` keeps your `.env` and data compatible. Major
version bumps (`v2.x`) get a dedicated migration note.

## General flow

```bash
cd ~/mnemo
git pull
docker compose pull
docker compose up -d
docker compose exec api alembic upgrade head
```

That's it for routine updates.

## Version-specific notes

### v1.0 → v1.1 (TBD)
- _placeholder; nothing yet_

### Rotating `MNEMO_ENCRYPTION_KEY`

Integration credentials (`integrations.config_encrypted`) are AES-GCM
encrypted at rest. If you suspect the key is compromised:

1. Generate a new key: `openssl rand -base64 32`
2. Set it as `MNEMO_ENCRYPTION_KEY_NEW` in `.env` (keep the old key as
   `MNEMO_ENCRYPTION_KEY`).
3. Run the rotation helper:
   ```bash
   docker compose exec api uv run python -m mnemo_api.scripts.rotate_key
   ```
   _(milestone-2 will ship this helper; until then, re-add integrations.)_
4. Swap keys: `MNEMO_ENCRYPTION_KEY=<new>`; drop `_NEW`.
5. `docker compose restart api workers`.

### Re-embedding (after changing `MNEMO_EMBED_MODEL`/`_DIM`)

See [ai-providers.md](ai-providers.md#local-ollama).
