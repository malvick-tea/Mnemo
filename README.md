# Mnemo

> Self-hosted AI second brain. Telegram is the UI.

Throw text, voice notes, photos, documents, or URLs at a Telegram bot. Mnemo
understands them, summarizes, tags, embeds, and stores them. Ask anything later
in plain language and get a grounded answer with citations to the original
captures.

```
You          → 🎙 voice note: "remember to look at the new pgvector hnsw paper"
Mnemo (bot)  → ✅ captured · transcribed in 4s · tagged #postgres #ml #papers

You          → /q what did I save about postgres last week?
Mnemo (bot)  → On Tuesday you flagged the new pgvector HNSW paper... [1]
               On Friday you saved an article about lock contention... [2]
               [1] [2]
```

**Philosophy.** Mnemo is a *capture-and-retrieval* tool, not a chat product.
The bot IS the product. Nothing leaves your infrastructure unless you turn on a
cloud LLM provider — and we tell you exactly what crosses the network and when.

## Quickstart (< 5 min on a clean VPS)

```bash
git clone https://github.com/yourname/mnemo.git
cd mnemo
./scripts/bootstrap.sh
```

`bootstrap.sh` will interactively ask for your Telegram bot token, allowed user
IDs, and AI provider choice. It writes `.env`, generates the Caddyfile, runs
`docker compose up -d`, waits for healthy, imports n8n workflows, and prints a
success URL.

Once green, message your bot. The first text you send becomes your first note.

## Features

| | |
|---|---|
| **Capture** | text, voice, photo, document (PDF/DOCX/EPUB/MD), URL, forwarded message |
| **Understand** | transcribe (faster-whisper), OCR (Qwen2-VL or GPT-4o), HTML extraction (trafilatura + Playwright fallback) |
| **Organize** | auto-summarize, auto-tag, semantic + full-text hybrid search |
| **Ask** | `/q <question>` — grounded RAG with inline citations and 👍/👎 feedback |
| **Surface** | daily digest, weekly review, "this relates to X you saved 3 months ago" |
| **Sync** | Notion, Obsidian (folder), Anki, Calendar |
| **Self-host** | one `docker compose up`. Caddy gets you HTTPS automatically. |
| **BYO models** | OpenRouter, OpenAI, or fully-local Ollama. Switch with one env var. |

## Architecture (TL;DR)

```
Telegram → Bot (aiogram 3) → Core API (FastAPI) ─┬─ Postgres (metadata + FTS)
                                                  ├─ Qdrant (embeddings)
                                                  ├─ Redis (queue + pub/sub)
                                                  ├─ MinIO (originals)
                                                  └─ n8n (heavy/branching pipelines)
                                                       │
                                       Workers (Dramatiq) — fast in-process jobs
```

The bot is a thin client. Heavy or branchy pipelines (URL scrape with fallback,
voice → transcribe → diarize → summarize → tag) live in n8n workflows you can
fork and edit visually. Fast jobs (embedding, short summaries) run in Dramatiq
workers for low latency.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full picture.

## Project status

🚧 **Phase 1 (MVP)** — text capture + RAG vertical slice. Voice, URL, photo,
document, forwards are coming next. See [PLAN.md](PLAN.md).

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — components, data model, RAG pipeline
- [docs/setup-vps.md](docs/setup-vps.md) — step-by-step Ubuntu 24.04 install
- [docs/ai-providers.md](docs/ai-providers.md) — swap OpenRouter ↔ Ollama
- [docs/n8n-workflows.md](docs/n8n-workflows.md) — fork and extend ingestion
- [docs/integrations/](docs/integrations/) — Notion, Obsidian, Anki
- [SECURITY.md](SECURITY.md) — threat model and disclosure

## License

MIT. See [LICENSE](LICENSE).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). PRs welcome — but please open an issue
first for anything bigger than a small fix.
