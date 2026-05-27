"""Query / RAG endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from mnemo_api.deps import CurrentUser, SessionDep
from mnemo_api.models import Query
from mnemo_api.schemas import Citation, QueryFeedbackIn, QueryIn, QueryOut
from mnemo_api.services.rag import answer_question

router = APIRouter(prefix="/v1/query", tags=["query"])


@router.post("", response_model=QueryOut)
async def query_endpoint(
    payload: QueryIn,
    user: CurrentUser,
    session: SessionDep,
    request: Request,
) -> QueryOut:
    state = request.app.state
    result = await answer_question(
        session=session,
        qdrant=state.qdrant,
        embedder=state.embedder,
        llm=state.llm,
        user_id=user.id,
        query=payload.query,
        top_k=payload.top_k,
    )
    await session.commit()
    return QueryOut(
        query_id=result.query_id,
        answer=result.answer,
        citations=[
            Citation(
                note_id=c.note_id,
                short_id=c.short_id,
                title=c.title,
                excerpt=c.excerpt,
                captured_at=c.captured_at,
                source_type=c.source_type,
                source_url=c.source_url,
            )
            for c in result.citations
        ],
        latency_ms=result.latency_ms,
        model_used=result.model_used,
    )


@router.post("/{query_id}/feedback", status_code=204)
async def query_feedback(
    query_id: UUID,
    payload: QueryFeedbackIn,
    user: CurrentUser,
    session: SessionDep,
) -> None:
    q = await session.get(Query, query_id)
    if q is None or q.user_id != user.id:
        raise HTTPException(404, "Query not found")
    q.user_feedback = payload.rating
    await session.commit()
