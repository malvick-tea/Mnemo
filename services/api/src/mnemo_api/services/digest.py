"""Daily digest and weekly review generation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo_api.config import get_settings
from mnemo_api.llm import LLMClient, Message, render_prompt
from mnemo_api.models import Note, NoteStatus


async def daily_digest(
    session: AsyncSession,
    llm: LLMClient,
    *,
    user_id: UUID,
    on_date: datetime | None = None,
) -> str:
    """Return a human-readable digest for the user's captures on `on_date`."""
    settings = get_settings()
    day = (on_date or datetime.now(UTC)).date()
    day_start = datetime.combine(day, datetime.min.time(), tzinfo=UTC)
    day_end = day_start + timedelta(days=1)

    rows = await session.execute(
        select(Note)
        .where(
            Note.user_id == user_id,
            Note.created_at >= day_start,
            Note.created_at < day_end,
            Note.status == NoteStatus.ready.value,
        )
        .order_by(Note.created_at)
    )
    today_notes = [
        {
            "short_id": str(n.id)[:8],
            "title": n.title,
            "summary": n.summary or "(no summary)",
        }
        for n in rows.scalars()
    ]

    prompt, fp = render_prompt(
        "daily_digest_v1",
        date=day.isoformat(),
        today_notes=today_notes,
        resurfaces=[],   # TODO(milestone-3): wire semantic resurfaces
    )
    completion = await llm.chat(
        [Message(role="user", content=prompt)],
        model=settings.model_rag,
        max_tokens=600,
        temperature=0.4,
        prompt_fingerprint=fp,
    )
    return completion.text.strip()


async def weekly_review(
    session: AsyncSession,
    llm: LLMClient,
    *,
    user_id: UUID,
    ending: datetime | None = None,
) -> str:
    settings = get_settings()
    end = ending or datetime.now(UTC)
    start = end - timedelta(days=7)

    rows = await session.execute(
        select(Note)
        .where(
            Note.user_id == user_id,
            Note.created_at >= start,
            Note.created_at < end,
            Note.status == NoteStatus.ready.value,
        )
        .order_by(Note.created_at)
    )
    notes = [
        {
            "captured_at": n.captured_at.isoformat(),
            "title": n.title,
            "summary": n.summary or "(no summary)",
        }
        for n in rows.scalars()
    ]

    prompt, fp = render_prompt(
        "weekly_review_v1", date=end.date().isoformat(), notes=notes
    )
    completion = await llm.chat(
        [Message(role="user", content=prompt)],
        model=settings.model_rag,
        max_tokens=900,
        temperature=0.5,
        prompt_fingerprint=fp,
    )
    return completion.text.strip()
