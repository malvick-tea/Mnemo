# Obsidian export

The `006-obsidian-export` n8n workflow writes one `.md` per note into a
folder you sync with Obsidian (Syncthing, Resilio, iCloud, Dropbox, …).

## Setup

1. Pick a folder on the VPS that your sync tool will mirror to your
   devices. Default: `/data/obsidian` inside the n8n container, mounted to
   a host path you choose in `docker-compose.yml`.
2. In your Obsidian vault config on a client, point at the synced folder
   (e.g. `~/Sync/mnemo-vault`).
3. Enable the integration in `/settings`.

## Output format

```markdown
---
mnemo_id: 3f1c2d8e-...-...
title: pgvector HNSW paper
captured_at: 2026-02-03T14:21:00Z
source_url: https://example.com/post
tags:
  - postgres
  - ml
  - papers
---

Body of the note (processed_content). Mnemo's summary appears as the first
blockquote:

> Notes on the new HNSW index for pgvector...
```

The `mnemo_id` frontmatter lets Mnemo recognize on the next sync that the
file already exists and update it in place rather than creating a duplicate.

## Known limitations

- One-way: edits in Obsidian aren't pulled back into Mnemo.
- Filename slug is derived from title; renaming a note can create a new
  file on the next sync (the old file isn't deleted automatically).
