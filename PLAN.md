# Mnemo — Execution Plan

> Phased execution log for delivering the Mnemo MVP per the mega-prompt.
> Each phase is a vertical slice that should be independently mergeable.

## Phase 0 — Foundation (this commit)

- [x] PLAN.md (this file)
- [x] ARCHITECTURE.md (distillation of mega-prompt §2, §5, §9)
- [x] README.md (quickstart + vision)
- [x] LICENSE (MIT)
- [x] CONTRIBUTING.md / SECURITY.md
- [x] Repository scaffolding per mega-prompt §4
- [x] `docker-compose.yml` + `docker-compose.dev.yml`
- [x] `.env.example` documenting every var
- [x] `Caddyfile.example`
- [x] `Makefile`
- [x] `scripts/bootstrap.sh`
- [x] ADR-001: choice of `uv` over `poetry`
- [x] ADR-002: hybrid search (RRF over pure vector)
- [x] ADR-003: n8n vs in-process workers split

## Phase 1 — Text-capture vertical slice (MVP core)

Goal: `text → bot → API → DB → embed (worker) → Qdrant → query → answer with citation`.

- [x] `services/api`: FastAPI scaffold, config, Postgres + Qdrant + Redis deps, healthz/readyz
- [x] Alembic migration `0001_initial.sql` with full schema from §5.1
- [x] `mnemo_api.llm` adapter with OpenRouter + Ollama clients
- [x] `mnemo_api.services.capture.create_text_note`
- [x] `mnemo_api.services.search.hybrid_search` (vector + tsvector + RRF)
- [x] `mnemo_api.services.rag.answer` with citation parser
- [x] `services/workers`: Dramatiq scaffold, `embed_note`, `summarize_note`, `tag_note`
- [x] `services/bot`: aiogram 3 scaffold, FSM, middlewares, `/start`, text handler, `/q`
- [x] Redis pub/sub for `note.ready.<user_id>` → bot edits message
- [x] Integration test: post a note, embed, query, assert citation

## Phase 2 — Other capture types

- [x] Voice capture — local `process_voice_note` actor (faster-whisper); n8n
      `002-voice-transcribe` kept as alternative path for milestone-3
- [x] URL capture — handler + n8n `001-url-ingest` (functional); callback
      chains into the text pipeline so chunks/embeddings/pub-sub fire
- [x] Photo capture — local `process_photo_note` actor calls the vision LLM
      (`MNEMO_MODEL_VISION` via OpenRouter) for OCR + scene description; n8n
      `003-photo-ocr` kept as alternative
- [x] Document capture — local `process_document_note` actor for
      PDF/DOCX/EPUB/MD/TXT extraction; n8n `004-document-parse` kept as
      alternative
- [x] Forward capture — handler preserves `forward_origin` provenance into
      `Note.source_metadata.forward`

### Phase 2 implementation notes

All four "heavy" types share the same shape:

```
bot handler → /v1/capture/<kind>  (MinIO upload, except forward/text/url)
            → create_<kind>_note  (Note row + enqueue process_<kind>_note)
            → worker actor        (extract → set processed_content)
            → process_text_note   (summarize, tag, chunk, embed, publish)
```

The URL bug fix in `routers/webhooks_n8n._handle_note_ready` chains the
n8n callback into `process_text_note` instead of leaving the note in
`processing` status. Same hand-off pattern that voice/photo/document use.

Worker container needs `ffmpeg` + `libgomp1` for faster-whisper; the
Dockerfile installs them. The vision path requires `OPENROUTER_API_KEY`
regardless of `MNEMO_LLM_PROVIDER` (Ollama-native vision is milestone-3).

## Phase 3 — Digest & integrations

- [ ] Daily digest cron (Dramatiq periodic actor)
- [ ] Weekly review
- [ ] Notion sync workflow `005`
- [ ] Obsidian export `006`
- [ ] Anki cards `007`

## Phase 4 — Polish

- [ ] Webapp admin (FastAPI + HTMX)
- [ ] Backup/restore scripts
- [ ] CI: lint + test + build images
- [ ] README screenshots via `scripts/seed_demo.py`
- [ ] `docs/setup-vps.md` walkthrough
- [ ] Threat model in `SECURITY.md`

## Decisions log

See `docs/decisions/` for ADRs.
