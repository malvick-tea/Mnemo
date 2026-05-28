# Obsidian export

A local Dramatiq actor (`obsidian_export.py`) writes one `.md` per ready
note into a folder you sync with Obsidian (Syncthing, Resilio, iCloud,
Dropbox, …). It runs every 30 minutes via the scheduler container.

## Setup

1. Pick a path inside the workers container that your sync tool will
   mirror to your devices. Default: `/data/obsidian` (mounted from the
   `obsidian_vault` Docker volume in `docker-compose.yml`). You can
   override per-user by storing `{"vault_path": "/data/obsidian/me"}`
   in the integration config.
2. Configure the integration in Mnemo:
   ```bash
   curl -X POST https://your.mnemo.example.com/v1/integrations \
     -H 'Authorization: Bearer <service-jwt>' \
     -H 'Content-Type: application/json' \
     -d '{
       "kind": "obsidian",
       "is_active": true,
       "config": {"vault_path": "/data/obsidian"}
     }'
   ```
3. Point your sync tool at the `obsidian_vault` Docker volume (find the
   host path via `docker volume inspect mnemo_obsidian_vault`).

## Output format

```markdown
---
id: 3f1c2d8e-1234-5678-1234-567812345678
title: "pgvector HNSW paper"
captured: 2026-02-03T14:21:00+00:00
source_type: url
source_url: https://example.com/post
tags: ["postgres", "ml", "papers"]
---

> Notes on the new HNSW index for pgvector...

Body of the note (processed_content goes here).
```

Filename pattern: `YYYY-MM-DD-<title-slug>-<short_id>.md`.

## Known limitations

- One-way: edits in Obsidian aren't pulled back into Mnemo.
- Updates create new files; the old file is left in place. Manual cleanup
  required if you rename or edit a note in Mnemo. Dedup by `id`
  frontmatter is on the milestone-3 roadmap.
- The export is per-user — multi-user setups should set distinct
  `vault_path` values to avoid cross-contamination.

## Alternative: n8n workflow

`n8n/workflows/006-obsidian-export.json` is a scaffold for moving this
to n8n. Activate it and remove `obsidian_export` from `scheduler.py`.
