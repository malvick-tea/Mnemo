"""Generate Anki cards for a single note via the LLM.

We use the existing `anki_cards_v1` prompt. Cards are parsed from JSON and
validated to two shapes: basic (front/back) and cloze (text). Invalid items
are dropped silently — the caller surfaces the count to the user.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo_api.config import get_settings
from mnemo_api.exceptions import NotFoundError, ProviderError
from mnemo_api.llm import LLMClient, Message, render_prompt
from mnemo_api.logging import get_logger
from mnemo_api.models import Note

log = get_logger(__name__)

_CLOZE_RE = re.compile(r"\{\{c\d+::[^{}]+\}\}")


@dataclass(slots=True)
class AnkiCard:
    type: str       # "basic" | "cloze"
    front: str | None = None
    back: str | None = None
    text: str | None = None

    def to_dict(self) -> dict[str, str]:
        if self.type == "cloze":
            return {"type": "cloze", "text": self.text or ""}
        return {"type": "basic", "front": self.front or "", "back": self.back or ""}


@dataclass(slots=True)
class AnkiCardsResult:
    note_id: UUID
    cards: list[AnkiCard]
    model_used: str


async def generate_cards(
    session: AsyncSession,
    llm: LLMClient,
    *,
    user_id: UUID,
    note_id: UUID,
) -> AnkiCardsResult:
    settings = get_settings()
    note = (
        await session.execute(
            select(Note).where(Note.id == note_id, Note.user_id == user_id)
        )
    ).scalar_one_or_none()
    if note is None:
        raise NotFoundError(f"Note {note_id} not found")

    content = (note.processed_content or note.raw_content or "").strip()
    if not content:
        return AnkiCardsResult(note_id=note_id, cards=[], model_used=settings.model_rag)

    prompt, fp = render_prompt(
        "anki_cards_v1", title=note.title, content=content[:8_000],
    )
    try:
        completion = await llm.chat(
            [Message(role="user", content=prompt)],
            model=settings.model_rag,
            max_tokens=1_200,
            temperature=0.4,
            response_format="json",
            prompt_fingerprint=fp,
        )
    except Exception as exc:  # noqa: BLE001
        raise ProviderError(f"Anki LLM call failed: {exc}") from exc

    cards = _parse_cards(completion.text)
    return AnkiCardsResult(
        note_id=note_id, cards=cards, model_used=completion.model
    )


def _parse_cards(raw: str) -> list[AnkiCard]:
    try:
        obj: Any = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("anki.parse.json_failed", raw=raw[:200])
        return []
    if not isinstance(obj, dict):
        return []
    items = obj.get("cards", [])
    if not isinstance(items, list):
        return []

    out: list[AnkiCard] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        kind = (item.get("type") or "").strip().lower()
        if kind == "cloze":
            text = (item.get("text") or "").strip()
            if text and _CLOZE_RE.search(text):
                out.append(AnkiCard(type="cloze", text=text))
        elif kind == "basic":
            front = (item.get("front") or "").strip()
            back = (item.get("back") or "").strip()
            if front and back:
                out.append(AnkiCard(type="basic", front=front, back=back))
        if len(out) >= 20:
            break
    return out
