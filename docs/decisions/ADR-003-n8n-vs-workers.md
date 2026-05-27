# ADR-003: n8n for branchy pipelines, Dramatiq workers for fast jobs

- **Status:** accepted
- **Date:** 2026-02-05

## Context

Captures produce background work: embedding, summarization, tagging, OCR,
transcription, URL scraping. Some jobs are simple and latency-sensitive
(text embedding: tens of ms). Others are branchy with fallbacks (URL scrape:
trafilatura → if empty, Playwright → if empty, Readability). Mega-prompt
calls for both worker tier and n8n; this ADR justifies the split.

## Decision

| Job | Where it runs | Why |
|---|---|---|
| `embed_note` | Dramatiq | Sub-second, no branching, hot path. |
| `summarize_note`, `tag_note` | Dramatiq | Pure LLM call, no fallback chain. |
| `daily_digest`, `weekly_review` | Dramatiq cron actor | Periodic, simple. |
| URL ingest (`001`) | n8n | Multi-step with fallback (Playwright). |
| Voice (`002`) | n8n | Optional diarization step, model swap, MinIO IO. |
| Photo OCR (`003`) | n8n | Vision model swap, prompt iteration. |
| Document parse (`004`) | n8n | Branch by mime type. |
| External sync (`005`-`007`) | n8n | User edits credentials; iteration in UI is the value. |
| Dead link check (`008`) | n8n | Scheduled, lots of HTTP, easier to visualize. |

The Mnemo Core API triggers n8n via webhook; n8n calls back to
`/v1/webhooks/n8n/{note-ready,note-failed}` with HMAC-signed payloads.

## Consequences

**Good:**
- End-users get a *visual* place to fork pipelines without forking Python.
  Switching the OCR model in `003-photo-ocr.json` is a 30-second change in
  the n8n UI; no rebuild, no redeploy.
- Hot-path jobs stay in-process, no network hop, no shared n8n queue.
- Clear test boundary: Dramatiq tasks test like normal Python; n8n
  workflows test against a payload fixture replay.

**Trade-off:**
- Two operational systems instead of one. Mitigated by shipping both in
  `docker-compose.yml` so users never run them separately.
- Two error surfaces (Dramatiq retries vs n8n retries). Both expose
  metrics; `docs/n8n-workflows.md` documents the conventions.

## Alternatives considered

- **All in Dramatiq.** Loses the user-editable workflow story, which is one
  of Mnemo's three differentiators per mega-prompt §1.1.
- **All in n8n.** n8n's per-execution overhead is wrong for hot-path
  embedding; you don't want a workflow boot for a 200-token embed.
- **Temporal / Prefect.** More powerful, but heavier ops burden for a
  self-hoster; n8n is one container with a friendly UI.
