# AI providers

Mnemo's LLM and embedding layers sit behind small interfaces, so swapping
providers is `.env` only — no code changes.

## Picking a setup

| Goal | LLM provider | Embed provider | Notes |
|---|---|---|---|
| Cheap, multi-model | OpenRouter | Ollama (bge-m3) | Default. Pay-per-token, embed stays local. |
| Fully local | Ollama | Ollama | Needs ≥ 8 GB GPU or be patient on CPU. |
| Premium quality | OpenRouter (Claude/GPT-4o) | OpenAI (text-embedding-3-small) | Best out-of-the-box quality. |
| Mixed | OpenRouter for RAG, Ollama for summary/tag | Ollama | Caps cost; only the rare RAG call hits the cloud. |

## Knobs in `.env`

```
MNEMO_LLM_PROVIDER=openrouter        # openrouter | ollama
MNEMO_EMBED_PROVIDER=ollama          # ollama | openai

# Per-job model routing
MNEMO_MODEL_SUMMARIZE=google/gemini-2.5-flash
MNEMO_MODEL_TAG=google/gemini-2.5-flash
MNEMO_MODEL_RAG=anthropic/claude-sonnet-4.6
MNEMO_MODEL_VISION=openai/gpt-4o

MNEMO_EMBED_MODEL=bge-m3
MNEMO_EMBED_DIM=1024                 # bge-m3=1024; text-embedding-3-small=1536
```

**Important:** if you change `MNEMO_EMBED_DIM` after first boot you must
re-embed every chunk. The Alembic-managed Qdrant collection is created at
the configured dim; mixing dims is impossible. To re-embed:

```bash
docker compose exec api alembic upgrade head
docker compose exec api uv run python -c "
import asyncio
from mnemo_api.config import get_settings
from qdrant_client import AsyncQdrantClient
async def go():
    s = get_settings()
    c = AsyncQdrantClient(url=s.qdrant_url)
    await c.delete_collection(s.qdrant_collection)
    await c.close()
asyncio.run(go())
"
# Then re-enqueue embed for every note (TODO: ship a make target for this).
```

## Local Ollama

On Linux: install [ollama.com](https://ollama.com), run
`ollama serve` on the host. Set:

```
OLLAMA_BASE_URL=http://172.17.0.1:11434      # docker bridge gateway
```

On macOS / Windows Docker Desktop:

```
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

Models we test against:

```bash
ollama pull bge-m3                # embeddings, 1024-dim
ollama pull llama3.1:8b-instruct  # summary + tagging
ollama pull qwen2.5:32b-instruct  # RAG answers (32 GB RAM recommended)
ollama pull qwen2.5-vl:7b         # vision
```

## Cost guardrails

Every LLM call logs estimated tokens. A per-user daily cap
(`MNEMO_USER_DAILY_TOKEN_CAP`, default 200 000) emits a warning past
threshold; future milestone routes the user to the local model when the cap
is hit (see TODO in `mnemo_api.services.rag`).

## Adding a new provider

1. Create `mnemo_api/llm/<provider>.py` with a class that implements
   `LLMClient.chat(...) -> CompletionResult`.
2. Add a branch in `mnemo_api.llm.factory.make_llm`.
3. Add a row to the table above.
4. PR.

Expected size: ~80 LOC. See `mnemo_api/llm/openrouter.py` for the
reference shape.
