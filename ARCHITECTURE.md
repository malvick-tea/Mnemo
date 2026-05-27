# Mnemo — Architecture

This document distils mega-prompt §2 (system), §5 (data), §9 (AI layer) and
serves as the entry point for new contributors. Goal: read this once and
understand the system in 20 minutes.

## 1. Components

```
┌──────────────────────┐
│  Telegram (user)     │
└──────────┬───────────┘
           │ long polling (dev) / webhook (prod)
┌──────────▼───────────┐         ┌──────────────────┐
│   Bot (aiogram 3)    │◄────────┤  Webapp (admin)  │  FastAPI + HTMX
└──────────┬───────────┘         └──────────────────┘
           │ HTTP/JSON, service JWT
┌──────────▼───────────┐
│  Core API (FastAPI)  │  auth · capture · query · settings · digest
└──────┬─────────┬─────┘
       │         │
       │         └─ webhook ──────────────────┐
       ▼                                       ▼
┌──────────────┐ ┌─────────────┐    ┌─────────────────┐
│  Postgres    │ │  Qdrant     │    │   n8n           │  workflows
│  metadata    │ │ embeddings  │    │  url/voice/...  │
└──────────────┘ └─────────────┘    └─────────┬───────┘
       ▲                ▲                     │
       │                │                     │
       └─── Workers ────┴──────── HTTP ───────┘
       (Dramatiq, Redis broker)         │
                                        ▼
                                  ┌─────────┐
                                  │  MinIO  │  original files
                                  └─────────┘
                                       │
                          ┌────────────┴───────────┐
                          │   AI providers          │
                          │   OpenRouter / Ollama   │
                          │   Whisper / Qwen2-VL    │
                          └─────────────────────────┘
```

### Why this split

- **Bot ↔ API:** the bot only speaks Telegram; all business logic is HTTP-facing
  so we can add a CLI, web UI, or other clients later without touching the bot.
- **Workers vs n8n:** sub-second jobs (text embedding, short summary) → Dramatiq
  workers. Heavy / branchy pipelines (URL → trafilatura → Playwright fallback →
  summary → tag → embed) → n8n where the workflow is visible and editable.
- **Postgres + Qdrant:** Postgres owns metadata and full-text search
  (`pg_trgm`, `tsvector`). Qdrant owns semantic search. The `/v1/query` route
  fuses them with Reciprocal Rank Fusion.
- **MinIO:** S3-compatible blob storage for originals (audio, images, PDFs).
  Trivially swappable for real S3.
- **Redis:** Dramatiq broker AND pub/sub channel `note.ready.<user_id>` so the
  bot can edit the placeholder message once async processing finishes.

### Communication

| from → to | protocol | notes |
|---|---|---|
| Bot → API | HTTPS / JSON | service JWT, correlation ID propagated |
| API → n8n | HTTPS webhook | HMAC-SHA256 signed payload, idempotency key |
| n8n → API | HTTPS webhook | same signing, replays safe |
| API ↔ Postgres / Qdrant / Redis / MinIO | direct TCP, internal docker network | |
| Workers ↔ DB | direct via asyncpg/SQLAlchemy | no HTTP indirection |
| Bot ↔ Redis pubsub | for `note.ready` events | bot subscribes per-user |

## 2. Data model

### Postgres (source of truth)

See `services/api/src/mnemo_api/migrations/versions/0001_initial.py` for the
canonical, executable schema. Tables:

- **users** — TG user, settings JSONB.
- **notes** — canonical unit of capture. `source_type` enum, `status` machine
  (`pending → processing → ready | failed`), `content_tsv` generated tsvector,
  `blob_keys[]` for MinIO references.
- **tags** + **note_tags** — many-to-many, with `confidence` and `source` (ai
  vs user).
- **chunks** — notes split for embedding. 1:N. `qdrant_point_id` mirrors the
  Qdrant point ID for fast back-resolution.
- **queries** — every `/v1/query` logged for analytics and RAG eval (cited
  note IDs, latency, model, user feedback).
- **integrations** — encrypted (AES-GCM) per-user external creds (Notion etc).
- **idempotency_keys** — webhook replay protection, 24h retention.

Indexes worth knowing:
- `notes_tsv_idx` — GIN on `content_tsv` (full-text search)
- `notes_trgm_idx` — GIN on `processed_content` with `gin_trgm_ops` (fuzzy)
- `notes_user_created_idx` — covering for `/v1/notes` listing

### Qdrant

- Collection: `mnemo_chunks`
- Vector size: 1024 (bge-m3 default) or 1536 (OpenAI). Init script reads from
  `MNEMO_EMBED_DIM`.
- Distance: cosine
- Payload-indexed: `user_id`, `tags`, `source_type`, `created_at` (range)
- HNSW: m=16, ef_construct=200 (good balance for ≤1M points)

### MinIO

Single bucket `mnemo-blobs`. Object key format:
`<user_id>/<yyyy>/<mm>/<note_id>/<original_filename>`.

## 3. Capture flow (canonical example: voice)

1. Bot receives a voice message, downloads from Telegram CDN.
2. Bot `POST /v1/capture/voice` multipart to API.
3. API validates (size ≤ 50 MB, mime ∈ audio), streams to MinIO, creates
   `notes` row with `status='pending'`.
4. API either enqueues Dramatiq `process_voice(note_id)` OR triggers n8n
   workflow `002-voice-transcribe` — choice is per-source-type setting on the
   user.
5. Worker / n8n: pull from MinIO → faster-whisper → write transcript →
   `status='processing'`.
6. Pipeline continues: summarize → tag → chunk → embed → upsert Qdrant →
   `status='ready'`.
7. n8n calls back `POST /v1/webhooks/n8n/note-ready { note_id }`.
8. API publishes Redis pub/sub event `note.ready.<user_id>`.
9. Bot (subscribed) edits the placeholder "🎙 Transcribing…" message with the
   final transcript + buttons.

## 4. Hybrid search

```python
def hybrid_search(user_id, query, top_k=8):
    q_vec = embed(query)
    vec_hits = qdrant.search(vector=q_vec,
                             filter={"user_id": user_id}, limit=20)
    fts_hits = pg.fetch("""
        SELECT id, ts_rank_cd(content_tsv,
                              websearch_to_tsquery('simple', $1)) AS r
        FROM notes WHERE user_id=$2 AND status='ready'
          AND content_tsv @@ websearch_to_tsquery('simple', $1)
        ORDER BY r DESC LIMIT 20
    """, query, user_id)
    fused = rrf_fuse([vec_hits, fts_hits], k=60)
    if settings.use_reranker:
        fused = rerank(query, fused, model="bge-reranker-v2-m3")[:top_k]
    return fused[:top_k]
```

The RAG prompt builds context from the top-k chunks, includes title +
`captured_at` per chunk, and instructs the LLM to cite by `[short_id]`. We
parse citations out and turn them into inline Telegram buttons.

See ADR-002 for the choice of RRF over pure vector or weighted-sum fusion.

## 5. AI layer

Single `LLMClient` interface in `mnemo_api/llm/base.py`:

```python
class LLMClient(Protocol):
    async def chat(self, messages: list[Message], *, model: str,
                   max_tokens: int = 1024, temperature: float = 0.2,
                   response_format: Literal["text", "json"] = "text"
                   ) -> CompletionResult: ...
```

Implementations: `OpenRouterClient`, `OllamaClient`. Adding a new provider is
~80 LOC — see `docs/ai-providers.md`.

Default routing (override in `.env`):

| job | model |
|---|---|
| summarization | `google/gemini-2.5-flash` (cheap, fast) |
| tagging | same as summarization |
| RAG answer | `anthropic/claude-sonnet-4.6` (strong) |
| vision | `qwen2.5-vl:7b` (local) or `gpt-4o` (cloud) |
| embedding | `bge-m3` via Ollama (default) or `text-embedding-3-small` |

### Prompts

All prompts live in `services/api/src/mnemo_api/llm/prompts/*.jinja2` and are
**versioned by filename** (`_v1`, `_v2`). The exact prompt filename used for a
call is logged with the request — bump the version when you change the prompt
and old query logs still reference the old prompt.

### Cost guardrails

- Every LLM call logs estimated tokens + cost.
- Per-user daily soft cap (`MNEMO_USER_DAILY_TOKEN_CAP`); when hit we fall back
  to the local model or warn the user.
- Bot exposes the running monthly cost in `/settings → Storage`.

## 6. Security at a glance

- TG user whitelist (`MNEMO_ALLOWED_TG_IDS`). No `/start` for outsiders.
- Internal services bind to the docker network; only Caddy faces the internet.
- Webhooks: HMAC-SHA256 + idempotency keys with 5-min timestamp window.
- Integration creds at rest: AES-GCM with key in `.env`.
- Logs strip message content by default; flip `MNEMO_LOG_PII=true` to debug.
- See [SECURITY.md](SECURITY.md) for the full threat model.

## 7. Observability

- Logs: structlog JSON, one line per request, correlation ID always present.
- Metrics: Prometheus on `:9100` (api), `:9101` (workers), `:9102` (bot).
  Custom: `captures_total{source_type}`, `query_latency_seconds`,
  `llm_tokens_total{provider,model}`.
- Tracing: OpenTelemetry SDK wired up; OFF by default.
- Healthchecks: `/v1/healthz` (live), `/v1/readyz` (checks DB/Qdrant/Redis).
