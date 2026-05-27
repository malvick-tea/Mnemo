# n8n workflows

This directory contains the Mnemo ingestion workflows as exported JSON. The
n8n container loads them on first start; you can edit any of them through
the n8n UI (HTTP Basic Auth, credentials in `.env`) and re-export to commit
your changes back.

## Conventions every workflow must follow

1. **Trigger:** Webhook node at path `/webhook/mnemo/<workflow-slug>`.
2. **Auth:** the first node after the trigger is a Function node
   `verify_hmac` that validates the `X-Mnemo-Signature` / `X-Mnemo-Timestamp`
   headers against `MNEMO_WEBHOOK_HMAC_SECRET`. On failure: return 401.
3. **Idempotency:** read the `Idempotency-Key` header; if a prior run with
   the same key succeeded, return its cached body (n8n's "Static Data"
   feature stores this).
4. **Retries:** every HTTP Request node has Retry On Fail enabled (3 attempts,
   exponential).
5. **Callback:** on success POST to `${MNEMO_API_BASE_URL}/v1/webhooks/n8n/note-ready`
   with the same HMAC signing scheme; on failure POST `note-failed`.
6. **Sticky notes:** the workflow's first sticky note documents purpose,
   trigger source, expected input shape, and known failure modes.

## Workflows in this directory

| Slug | Purpose | Phase |
|---|---|---|
| `001-url-ingest` | fetch URL, extract readable text, summarize, tag, embed | 1 (skeleton) |
| `002-voice-transcribe` | download from MinIO, faster-whisper, summarize, embed | 2 |
| `003-photo-ocr` | vision OCR + scene description | 2 |
| `004-document-parse` | branch by mime (PDF/DOCX/EPUB/MD), summarize, embed | 2 |
| `005-notion-sync` | scheduled push of new notes to a Notion DB | 3 |
| `006-obsidian-export` | scheduled write of `.md` to a synced folder | 3 |
| `007-anki-generate` | on-demand generate Cloze/Q&A cards via LLM | 3 |
| `008-dead-link-checker` | weekly HEAD-check URLs, mark dead ones | 3 |

For Phase 1, only `001-url-ingest` has a usable scaffold; the rest are
present as placeholders documented in `docs/n8n-workflows.md` and will be
filled in milestone-2.

## Importing

Workflows are auto-imported by the API on first boot via `scripts/n8n_import.sh`.
To re-import after edits:

```bash
make n8n-import
```

## Credentials

`credentials.example.json` lists the credential records each workflow
expects. They're created interactively in the n8n UI; we never check in
plaintext credentials.
