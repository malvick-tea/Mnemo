# Notion sync

The `005-notion-sync` n8n workflow pushes new and updated notes to a Notion
database you own. It runs every 15 minutes (Phase-3 scaffold; sketch in
this commit, full sync in milestone-3).

## Setup

1. Create a Notion **internal integration**:
   https://www.notion.so/profile/integrations → New integration.
   Save the secret (`secret_...`).
2. Create or pick a Notion database. Share it with the integration
   (top-right `Share` → invite by integration name).
3. In Mnemo: `/settings` → Integrations → Notion → paste secret + DB ID.

## How it works

- Mnemo queries `/v1/notes?from=last_synced_at` to get fresh notes.
- For each note, the workflow upserts a Notion page with properties:
  - **Title** → `note.title`
  - **Summary** → `note.summary`
  - **Tags** (multi-select) → `note.tags[*].name`
  - **Captured** (date) → `note.captured_at`
  - **Source URL** → `note.source_url`
  - **Body** (page content) → `note.processed_content`
- Mnemo `last_synced_at` is updated only on a successful round.

## Known limitations

- Deletes don't propagate to Notion yet (the page stays).
- Page-content sync is one-way (Mnemo → Notion). Edits in Notion are not
  reflected back.
- We cap each batch at 100 notes per cycle to avoid Notion rate limits.

## Troubleshooting

- Pages aren't appearing → check the n8n execution log for the cycle;
  401 means the secret was revoked or the DB isn't shared with the
  integration.
- Properties show up as text instead of multi-select → ensure the Notion
  DB already has a `Tags` multi-select column with at least one option
  defined.
