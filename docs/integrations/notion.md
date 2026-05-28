# Notion sync

A local Dramatiq actor (`notion_sync.py`) pushes new ready notes to a
Notion database you own. It runs every 15 minutes via the scheduler
container.

## Setup

1. Create a Notion **internal integration**:
   https://www.notion.so/profile/integrations → New integration.
   Save the secret (`secret_...`).
2. Create or pick a Notion database. Share it with the integration
   (top-right `Share` → invite by integration name).
3. Configure the integration in Mnemo:
   ```bash
   curl -X POST https://your.mnemo.example.com/v1/integrations \
     -H 'Authorization: Bearer <service-jwt>' \
     -H 'Content-Type: application/json' \
     -d '{
       "kind": "notion",
       "is_active": true,
       "config": {
         "integration_token": "secret_xxx",
         "database_id": "<32-hex DB id>"
       }
     }'
   ```
   Or use the webapp at `/admin/integrations` once authentication is wired.

## How it works

- Every 15 min the scheduler enqueues `run_notion_sync_for_all_users`.
- For each active Notion integration:
  - Decrypt config (AES-GCM at rest).
  - List ready notes created after `Integration.last_synced_at` (cap 50/run).
  - POST one Notion page per note with properties:
    - **Name** (title) → `note.title`
    - **Captured** (date) → `note.captured_at`
    - **Source** (select) → `note.source_type`
    - **URL** → `note.source_url` (if present)
    - **Tags** (multi-select) → up to 10 tag names
    - **Body** → summary or processed_content as a paragraph block
  - On success: bump `last_synced_at`.

## Notion DB schema (required columns)

| Column   | Type           | Required |
|----------|----------------|----------|
| Name     | Title          | yes      |
| Captured | Date           | yes      |
| Source   | Select         | yes      |
| URL      | URL            | optional |
| Tags     | Multi-select   | optional |

Mnemo will use whatever options already exist on `Source` and `Tags`;
if a value is missing, Notion silently rejects the property. Pre-seed
the `Source` select with `text/voice/photo/document/url/forward`.

## Known limitations

- One-way: edits in Notion are not synced back.
- Updates aren't yet detected — Mnemo creates a new page per run on
  changed notes. Dedup by `note.id` is on the milestone-3 roadmap.
- Deletes don't propagate.
- Batches cap at 50 notes/run to stay under Notion rate limits.

## Alternative: n8n workflow

`n8n/workflows/005-notion-sync.json` ships as an inactive scaffold for
users who prefer Notion sync in n8n (visual customization). Activate it
in the n8n UI and disable the local worker by removing the
`notion_sync` job from `scheduler.py`.
