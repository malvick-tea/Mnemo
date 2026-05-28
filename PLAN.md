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

- [x] Daily digest cron via APScheduler + `run_daily_digest_for_all_users`
      actor + bot listener on `digest.daily.<user_id>`
- [x] Weekly review endpoint (`GET /v1/digest/weekly`)
- [x] Notion sync — local `notion_sync.py` actor (15-min cron) pushes
      ready notes to user's configured Notion DB
- [x] Obsidian export — local `obsidian_export.py` actor (30-min cron)
      writes `.md` per note into `/data/obsidian` (Docker volume)
- [x] Anki cards — `/v1/notes/{id}/anki` endpoint + bot `/anki <short_id>`
      command + 🎴 inline button. Cards delivered as a Telegram message;
      AnkiConnect direct-push deferred to milestone-3

Per ADR-003 these stay in local Dramatiq actors. n8n workflows 005-007
ship as inactive scaffolds for users who prefer the visual editor.

## Phase 4 — Polish

- [x] Webapp admin — minimal FastAPI + HTMX read-only UI at
      `/admin/` (via Caddy basicauth). Notes list, recent queries,
      tag cloud. See `services/webapp/`.
- [x] Backup/restore scripts (source `.env`, MinIO skip guard)
- [x] CI: lint + test + build images (`.github/workflows/`)
- [ ] README screenshots via `scripts/seed_demo.py`
- [ ] `docs/setup-vps.md` walkthrough — currently a placeholder
- [ ] Threat model in `SECURITY.md` — currently a placeholder

### Bug fixes shipped alongside Phase 3+4

- `_handle_note_ready` left URL notes stuck in `processing`; now chains
  into `process_text_note` for chunk+embed+publish.
- `hybrid_search` was reporting all sources as `("rrf",)`; `_rrf_fuse`
  now tracks contributing retrievers via `_FusionEntry`.
- Bot listener relied on a `mnemo:user:<id>` Redis mapping that nothing
  populated → moved `tg_user_id` into the pub/sub payload itself.
- `digest.daily.<user_id>` channel had no bot listener → renamed
  `listen_note_ready` → `listen_bot_events` and subscribed to both.
- `delete_note` left Qdrant orphans → now filtered-delete by `note_id`.
- `make_embedder("openai")` used the OpenRouter API key (contradicting
  its own error message); added a real `OPENAI_API_KEY` setting.
- `capture.py` router used `redis: Redis = get_redis` (passes the
  function as a default), now `Annotated[Redis, Depends(get_redis)]`
  via new `RedisDep`/`MinioDep`/`QdrantDep`/`LLMDep`/`EmbedderDep`.
- `backup.sh` didn't source `.env`, so MINIO env vars were missing.

## Decisions log

See `docs/decisions/` for ADRs.
