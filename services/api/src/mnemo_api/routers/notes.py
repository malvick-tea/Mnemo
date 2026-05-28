"""Note CRUD-ish endpoints (GET/PATCH/DELETE + listing)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from qdrant_client.http.models import FieldCondition, Filter, FilterSelector, MatchValue
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo_api.config import get_settings
from mnemo_api.deps import CurrentUser, LLMDep, QdrantDep, SessionDep
from mnemo_api.exceptions import MnemoError
from mnemo_api.logging import get_logger
from mnemo_api.models import Note, NoteTag, Tag
from mnemo_api.schemas import AnkiCardOut, AnkiCardsOut, NoteOut, NotePatch, TagOut
from mnemo_api.services.anki import generate_cards

router = APIRouter(prefix="/v1", tags=["notes"])
log = get_logger(__name__)


@router.get("/notes/{note_id}", response_model=NoteOut)
async def get_note(note_id: UUID, user: CurrentUser, session: SessionDep) -> NoteOut:
    note = await session.get(Note, note_id)
    if note is None or note.user_id != user.id:
        raise HTTPException(404, "Note not found")
    tags = await _tags_for(session, note_id)
    return _to_dto(note, tags)


@router.patch("/notes/{note_id}", response_model=NoteOut)
async def patch_note(
    note_id: UUID, payload: NotePatch, user: CurrentUser, session: SessionDep
) -> NoteOut:
    note = await session.get(Note, note_id)
    if note is None or note.user_id != user.id:
        raise HTTPException(404, "Note not found")
    if payload.title is not None:
        note.title = payload.title
    if payload.summary is not None:
        note.summary = payload.summary
    if payload.processed_content is not None:
        note.processed_content = payload.processed_content

    for tag_name in payload.add_tags:
        tag = await _get_or_create_user_tag(session, user.id, tag_name.lower().strip())
        await session.merge(NoteTag(note_id=note_id, tag_id=tag.id, source="user", confidence=1.0))
    for tag_name in payload.remove_tags:
        await session.execute(
            NoteTag.__table__.delete().where(
                NoteTag.note_id == note_id,
                NoteTag.tag_id.in_(
                    select(Tag.id).where(
                        Tag.user_id == user.id,
                        Tag.name == tag_name.lower().strip(),
                    )
                ),
            )
        )

    await session.commit()
    tags = await _tags_for(session, note_id)
    return _to_dto(note, tags)


@router.delete("/notes/{note_id}", status_code=204)
async def delete_note(
    note_id: UUID,
    user: CurrentUser,
    session: SessionDep,
    qdrant: QdrantDep,
) -> None:
    note = await session.get(Note, note_id)
    if note is None or note.user_id != user.id:
        raise HTTPException(404, "Note not found")

    await session.delete(note)
    await session.commit()

    # Drop the orphaned vectors. Filtered delete is O(matching), and we
    # tolerate failure here — the row is gone, the search index will be
    # consistent on the next periodic re-sync (milestone-3).
    try:
        await qdrant.delete(
            collection_name=get_settings().qdrant_collection,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="note_id", match=MatchValue(value=str(note_id))
                        )
                    ]
                )
            ),
        )
    except Exception:  # noqa: BLE001
        log.exception("notes.delete.qdrant_cleanup_failed", note_id=str(note_id))


@router.get("/notes", response_model=list[NoteOut])
async def list_notes(
    user: CurrentUser,
    session: SessionDep,
    q: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[NoteOut]:
    stmt = select(Note).where(Note.user_id == user.id)
    if from_ is not None:
        stmt = stmt.where(Note.captured_at >= from_)
    if to is not None:
        stmt = stmt.where(Note.captured_at < to)
    if tag is not None:
        stmt = stmt.join(NoteTag, NoteTag.note_id == Note.id).join(
            Tag, Tag.id == NoteTag.tag_id
        ).where(Tag.user_id == user.id, Tag.name == tag.lower().strip())
    if q is not None and q.strip():
        stmt = stmt.where(Note.content_tsv.op("@@")(func.websearch_to_tsquery("simple", q)))
    stmt = stmt.order_by(Note.created_at.desc()).limit(limit)
    res = await session.execute(stmt)
    notes = res.scalars().unique().all()
    out: list[NoteOut] = []
    for n in notes:
        tags = await _tags_for(session, n.id)
        out.append(_to_dto(n, tags))
    return out


@router.post("/notes/{note_id}/anki", response_model=AnkiCardsOut)
async def generate_anki(
    note_id: UUID,
    user: CurrentUser,
    session: SessionDep,
    llm: LLMDep,
) -> AnkiCardsOut:
    try:
        result = await generate_cards(
            session, llm, user_id=user.id, note_id=note_id
        )
    except MnemoError as exc:
        raise HTTPException(exc.http_status, str(exc)) from exc
    return AnkiCardsOut(
        note_id=result.note_id,
        cards=[AnkiCardOut(**c.to_dict()) for c in result.cards],
        model_used=result.model_used,
    )


@router.get("/tags", response_model=list[TagOut])
async def list_tags(user: CurrentUser, session: SessionDep) -> list[TagOut]:
    res = await session.execute(
        select(Tag.id, Tag.name, Tag.color, func.count(NoteTag.note_id).label("cnt"))
        .join(NoteTag, NoteTag.tag_id == Tag.id, isouter=True)
        .where(Tag.user_id == user.id)
        .group_by(Tag.id, Tag.name, Tag.color)
        .order_by(func.count(NoteTag.note_id).desc())
    )
    return [
        TagOut(id=r.id, name=r.name, color=r.color, count=int(r.cnt))
        for r in res
    ]


# ─── helpers ────────────────────────────────────────────────────────────────


async def _tags_for(session: AsyncSession, note_id: UUID) -> list[TagOut]:
    rows = await session.execute(
        select(Tag.id, Tag.name, Tag.color)
        .join(NoteTag, NoteTag.tag_id == Tag.id)
        .where(NoteTag.note_id == note_id)
    )
    return [TagOut(id=r.id, name=r.name, color=r.color) for r in rows]


async def _get_or_create_user_tag(
    session: AsyncSession, user_id: UUID, name: str
) -> Tag:
    res = await session.execute(
        select(Tag).where(Tag.user_id == user_id, Tag.name == name)
    )
    existing = res.scalar_one_or_none()
    if existing is not None:
        return existing
    tag = Tag(user_id=user_id, name=name)
    session.add(tag)
    await session.flush()
    return tag


def _to_dto(note: Note, tags: list[TagOut]) -> NoteOut:
    return NoteOut(
        id=note.id,
        source_type=note.source_type,  # type: ignore[arg-type]
        title=note.title,
        summary=note.summary,
        raw_content=note.raw_content,
        processed_content=note.processed_content,
        source_url=note.source_url,
        tags=tags,
        status=note.status,
        error_message=note.error_message,
        captured_at=note.captured_at,
        created_at=note.created_at,
        processed_at=note.processed_at,
        source_metadata=note.source_metadata,
    )
