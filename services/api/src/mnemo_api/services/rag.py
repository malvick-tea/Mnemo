"""RAG: build a context, run the LLM, parse out citations.

The prompt instructs the LLM to use short citation tokens `[abcdef12]`; we
parse those out and look up the corresponding notes for the response.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from uuid import UUID

from qdrant_client import AsyncQdrantClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo_api.config import get_settings
from mnemo_api.llm import LLMClient, Message, render_prompt
from mnemo_api.llm.base import Embedder
from mnemo_api.logging import get_logger
from mnemo_api.metrics import query_latency_seconds, query_total, search_hits
from mnemo_api.models import Note, Query
from mnemo_api.services.search import SearchHit, hybrid_search

log = get_logger(__name__)

_CITATION_RE = re.compile(r"\[([0-9a-f]{8})\]")


@dataclass(slots=True)
class CitationOut:
    note_id: UUID
    short_id: str
    title: str | None
    excerpt: str
    captured_at: str
    source_type: str
    source_url: str | None


@dataclass(slots=True)
class RagResult:
    query_id: UUID
    answer: str
    citations: list[CitationOut]
    latency_ms: int
    model_used: str


async def answer_question(
    *,
    session: AsyncSession,
    qdrant: AsyncQdrantClient,
    embedder: Embedder,
    llm: LLMClient,
    user_id: UUID,
    query: str,
    top_k: int = 8,
) -> RagResult:
    settings = get_settings()
    t0 = time.perf_counter()

    try:
        hits = await hybrid_search(
            session=session,
            qdrant=qdrant,
            embedder=embedder,
            user_id=user_id,
            query=query,
            top_k=top_k,
        )
    except Exception:
        query_total.labels(outcome="error").inc()
        raise
    search_hits.labels(retriever="fused").observe(len(hits))

    if not hits:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        query_latency_seconds.observe(latency_ms / 1000.0)
        query_total.labels(outcome="empty").inc()
        out = RagResult(
            query_id=UUID(int=0),
            answer=(
                "I couldn't find anything in your notes that matches that. "
                "Try rephrasing or saving more on the topic first."
            ),
            citations=[],
            latency_ms=latency_ms,
            model_used=settings.model_rag,
        )
        query_id = await _log_query(session, user_id, query, out)
        out.query_id = query_id
        return out

    snippets = [
        {
            "short_id": str(h.note_id)[:8],
            "title": h.title,
            "captured_at": h.captured_at,
            "source_type": h.source_type,
            "content": h.content[:1200],
        }
        for h in hits
    ]
    prompt, fp = render_prompt("rag_answer_v1", query=query, snippets=snippets)
    try:
        completion = await llm.chat(
            [
                Message(role="system", content="You are Mnemo, a careful retrieval assistant."),
                Message(role="user", content=prompt),
            ],
            model=settings.model_rag,
            max_tokens=900,
            temperature=0.2,
            prompt_fingerprint=fp,
        )
    except Exception:
        query_total.labels(outcome="error").inc()
        raise

    cited_shorts = set(_CITATION_RE.findall(completion.text))
    citations = await _build_citations(session, hits, cited_shorts)

    latency_ms = int((time.perf_counter() - t0) * 1000)
    query_latency_seconds.observe(latency_ms / 1000.0)
    query_total.labels(outcome="ok").inc()
    out = RagResult(
        query_id=UUID(int=0),
        answer=completion.text,
        citations=citations,
        latency_ms=latency_ms,
        model_used=completion.model,
    )
    query_id = await _log_query(session, user_id, query, out)
    out.query_id = query_id
    return out


async def _build_citations(
    session: AsyncSession, hits: list[SearchHit], cited_shorts: set[str]
) -> list[CitationOut]:
    relevant = {h.note_id: h for h in hits if str(h.note_id)[:8] in cited_shorts}
    if not relevant:
        # Model didn't cite — surface top 3 as soft citations so the user
        # can still see what informed the answer.
        relevant = {h.note_id: h for h in hits[:3]}

    rows = await session.execute(select(Note).where(Note.id.in_(relevant.keys())))
    notes_by_id = {n.id: n for n in rows.scalars()}
    out: list[CitationOut] = []
    for note_id, hit in relevant.items():
        note = notes_by_id.get(note_id)
        excerpt = (hit.content[:280] + "…") if len(hit.content) > 280 else hit.content
        out.append(
            CitationOut(
                note_id=note_id,
                short_id=str(note_id)[:8],
                title=(note.title if note else None) or hit.title,
                excerpt=excerpt,
                captured_at=hit.captured_at,
                source_type=hit.source_type,
                source_url=(note.source_url if note else None) or hit.source_url,
            )
        )
    return out


async def _log_query(session: AsyncSession, user_id: UUID, query: str, result: RagResult) -> UUID:
    q = Query(
        user_id=user_id,
        query_text=query,
        response_text=result.answer,
        cited_note_ids=[c.note_id for c in result.citations],
        latency_ms=result.latency_ms,
        model_used=result.model_used,
    )
    session.add(q)
    await session.flush()
    return q.id
