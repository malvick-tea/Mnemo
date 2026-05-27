"""Note CRUD-ish endpoints (GET/PATCH/DELETE + listing)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from mnemo_api.deps import CurrentUser, SessionDep
from mnemo_api.models import Note, NoteStatus, NoteTag, Tag
from mnemo_api.schemas import NoteOut, NotePatch, TagOut

router = APIRouter(prefix="/v1", tags=["notes"])


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
async def delete_note(note_id: UUID, user: CurrentUser, session: SessionDep) -> None:
    note = await session.get(Note, note_id)
    if note is None or note.user_id != user.id:
        raise HTTPException(404, "Note not found")
    # Soft-delete: mark failed-style? For v1 we hard-delete and rely on
    # ON DELETE CASCADE to remove chunks; vector cleanup happens in a worker.
    await session.delete(note)
    await session.commit()


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


async def _tags_for(session: SessionDep, note_id: UUID) -> list[TagOut]:
    rows = await session.execute(
        select(Tag.id, Tag.name, Tag.color)
        .join(NoteTag, NoteTag.tag_id == Tag.id)
        .where(NoteTag.note_id == note_id)
    )
    return [TagOut(id=r.id, name=r.name, color=r.color) for r in rows]


async def _get_or_create_user_tag(session: SessionDep, user_id: UUID, name: str) -> Tag:
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
        captured_at=note.captured_at,
        created_at=note.created_at,
        processed_at=note.processed_at,
        source_metadata=note.source_metadata,
    )


# selectinload is intentionally imported but unused here — kept as a marker
# for the future per-note tag eager-load optimisation.
_ = selectinload
