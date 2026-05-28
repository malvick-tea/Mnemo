"""Propose tags for a note using the user's existing tag vocabulary."""

from __future__ import annotations

import json
import re
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo_api.config import get_settings
from mnemo_api.llm import LLMClient, Message, render_prompt
from mnemo_api.logging import get_logger
from mnemo_api.models import Note, NoteTag, Tag

log = get_logger(__name__)

_TAG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{0,29}$")


async def suggest_and_apply_tags(
    session: AsyncSession,
    llm: LLMClient,
    *,
    note_id: UUID,
    user_id: UUID,
    content: str,
) -> list[str]:
    """Suggest 1-5 tags, persist them, and return the applied tag names."""
    settings = get_settings()

    # Pull current top tag vocabulary so the LLM prefers reuse.
    rows = await session.execute(
        select(Tag.name, func.count(NoteTag.note_id).label("cnt"))
        .join(NoteTag, NoteTag.tag_id == Tag.id, isouter=True)
        .where(Tag.user_id == user_id)
        .group_by(Tag.name)
        .order_by(func.count(NoteTag.note_id).desc())
        .limit(50)
    )
    existing = [r.name for r in rows]

    prompt, fp = render_prompt("tag_suggest_v1", existing_tags=existing, content=content[:4000])
    completion = await llm.chat(
        [Message(role="user", content=prompt)],
        model=settings.model_tag,
        max_tokens=200,
        temperature=0.0,
        response_format="json",
        prompt_fingerprint=fp,
    )

    proposed = _parse_tags(completion.text)
    if not proposed:
        log.warning("tagging.parse_failed", note_id=str(note_id), raw=completion.text[:200])
        return []

    note = await session.get(Note, note_id)
    if note is None:
        return []
    applied: list[str] = []
    for name in proposed:
        tag = await _get_or_create_tag(session, user_id=user_id, name=name)
        link = NoteTag(note_id=note_id, tag_id=tag.id, source="ai", confidence=1.0)
        await session.merge(link)
        applied.append(name)
    return applied


def _parse_tags(raw: str) -> list[str]:
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return []
    tags = obj.get("tags", []) if isinstance(obj, dict) else []
    out: list[str] = []
    seen = set()
    for t in tags:
        if not isinstance(t, str):
            continue
        clean = t.strip().lower().lstrip("#")
        if _TAG_RE.match(clean) and clean not in seen:
            out.append(clean)
            seen.add(clean)
        if len(out) >= 5:
            break
    return out


async def _get_or_create_tag(session: AsyncSession, *, user_id: UUID, name: str) -> Tag:
    res = await session.execute(select(Tag).where(Tag.user_id == user_id, Tag.name == name))
    existing = res.scalar_one_or_none()
    if existing is not None:
        return existing
    tag = Tag(user_id=user_id, name=name)
    session.add(tag)
    await session.flush()
    return tag
