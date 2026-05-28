"""Hybrid search: Qdrant + Postgres FTS, fused via RRF.

See ADR-002 for the rationale (no per-corpus tuning required).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import (
    FieldCondition,
    Filter,
    MatchValue,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo_api.config import get_settings
from mnemo_api.llm.base import Embedder
from mnemo_api.logging import get_logger

log = get_logger(__name__)


@dataclass(slots=True, frozen=True)
class SearchHit:
    note_id: UUID
    chunk_id: UUID
    score: float
    rrf_score: float
    source: tuple[str, ...]   # which retrievers contributed ("vec","fts")
    content: str
    title: str | None
    captured_at: str
    source_type: str
    source_url: str | None


@dataclass(slots=True)
class _FusionEntry:
    note_id: UUID
    score: float = 0.0
    sources: set[str] = field(default_factory=set)


async def hybrid_search(
    *,
    session: AsyncSession,
    qdrant: AsyncQdrantClient,
    embedder: Embedder,
    user_id: UUID,
    query: str,
    top_k: int = 8,
    candidate_pool: int = 20,
    rrf_k: int = 60,
) -> list[SearchHit]:
    """Combine vector + tsvector candidates with RRF, return top-k."""
    settings = get_settings()
    q_vec = await embedder.embed_one(query)

    vec_resp = await qdrant.search(
        collection_name=settings.qdrant_collection,
        query_vector=q_vec,
        query_filter=Filter(
            must=[
                FieldCondition(key="user_id", match=MatchValue(value=str(user_id))),
            ]
        ),
        limit=candidate_pool,
        with_payload=True,
    )

    vec_ranked: list[tuple[UUID, UUID, float]] = [
        (
            UUID(point.payload["chunk_id"]),  # type: ignore[index]
            UUID(point.payload["note_id"]),  # type: ignore[index]
            float(point.score),
        )
        for point in vec_resp
    ]

    fts_rows = await session.execute(
        text(
            """
            SELECT c.id AS chunk_id, n.id AS note_id,
                   ts_rank_cd(n.content_tsv,
                              websearch_to_tsquery('simple', :q)) AS r
              FROM notes n
              JOIN chunks c ON c.note_id = n.id
             WHERE n.user_id = :uid
               AND n.status = 'ready'
               AND n.content_tsv @@ websearch_to_tsquery('simple', :q)
             ORDER BY r DESC
             LIMIT :lim
            """
        ),
        {"q": query, "uid": user_id, "lim": candidate_pool},
    )
    fts_ranked: list[tuple[UUID, UUID, float]] = [
        (r.chunk_id, r.note_id, float(r.r)) for r in fts_rows
    ]

    fused = _rrf_fuse(
        rankings=[vec_ranked, fts_ranked],
        labels=("vec", "fts"),
        k=rrf_k,
    )
    if not fused:
        return []

    top_chunk_ids = [chunk_id for chunk_id, _ in fused[:top_k]]
    chunks = await _hydrate_chunks(session, top_chunk_ids)

    hits: list[SearchHit] = []
    for chunk_id, entry in fused[:top_k]:
        chunk_meta = chunks.get(chunk_id)
        if chunk_meta is None:
            continue
        hits.append(
            SearchHit(
                note_id=entry.note_id,
                chunk_id=chunk_id,
                score=chunk_meta["score"],
                rrf_score=entry.score,
                source=tuple(sorted(entry.sources)) or ("rrf",),
                content=chunk_meta["content"],
                title=chunk_meta["title"],
                captured_at=chunk_meta["captured_at"],
                source_type=chunk_meta["source_type"],
                source_url=chunk_meta["source_url"],
            )
        )
    log.info(
        "search.hybrid.completed",
        query_len=len(query),
        vec_hits=len(vec_ranked),
        fts_hits=len(fts_ranked),
        returned=len(hits),
    )
    return hits


def _rrf_fuse(
    *,
    rankings: list[list[tuple[UUID, UUID, float]]],
    labels: tuple[str, ...],
    k: int,
) -> list[tuple[UUID, _FusionEntry]]:
    """Reciprocal Rank Fusion. Returns chunk_id → (note_id, score, sources)."""
    entries: dict[UUID, _FusionEntry] = {}
    for label, ranking in zip(labels, rankings, strict=False):
        for rank, (chunk_id, note_id, _raw_score) in enumerate(ranking, start=1):
            entry = entries.get(chunk_id)
            if entry is None:
                entry = _FusionEntry(note_id=note_id)
                entries[chunk_id] = entry
            entry.score += 1.0 / (k + rank)
            entry.sources.add(label)
    fused = list(entries.items())
    fused.sort(key=lambda kv: kv[1].score, reverse=True)
    return fused


async def _hydrate_chunks(
    session: AsyncSession, chunk_ids: list[UUID]
) -> dict[UUID, dict[str, object]]:
    if not chunk_ids:
        return {}
    rows = await session.execute(
        text(
            """
            SELECT c.id, c.content, n.title, n.captured_at, n.source_type, n.source_url
              FROM chunks c
              JOIN notes n ON n.id = c.note_id
             WHERE c.id = ANY(:ids)
            """
        ),
        {"ids": chunk_ids},
    )
    out: dict[UUID, dict[str, object]] = {}
    for r in rows:
        out[r.id] = {
            "content": r.content,
            "title": r.title,
            "captured_at": r.captured_at.isoformat() if r.captured_at else "",
            "source_type": r.source_type,
            "source_url": r.source_url,
            "score": 0.0,
        }
    return out
