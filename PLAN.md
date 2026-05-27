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

- [ ] Voice capture (faster-whisper) — handler + n8n workflow `002`
- [ ] URL capture (trafilatura + Playwright fallback) — handler + n8n workflow `001`
- [ ] Photo OCR — handler + n8n workflow `003`
- [ ] Document parsing — handler + n8n workflow `004`
- [ ] Forward capture — handler

Phase 2 handlers in `services/bot` are stubbed in this commit with `NotImplementedError("TODO(milestone-2)")` to keep router wiring honest.

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
