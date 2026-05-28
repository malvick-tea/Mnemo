"""``/anki`` command and inline callback handler.

Usage:
- `/anki <short_id>` — generate cards for a specific note
- Tap the 🎴 Anki button on a note message (callback `note:anki:<note_id>`)

The cards come back from the API; we format them as a Telegram message
the user can copy-paste into Anki. Direct AnkiConnect push is milestone-3
because it requires reaching the user's machine from the server.
"""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from mnemo_bot.api_client import ApiClient
from mnemo_bot.logging import get_logger

log = get_logger(__name__)
router = Router(name="anki")

_SHORT_ID_RE = re.compile(r"^[0-9a-f]{8}$")


@router.message(Command("anki"))
async def anki_command(
    message: Message,
    command: CommandObject,
    api: ApiClient,
    tg_user_id: int,
) -> None:
    arg = (command.args or "").strip().lower()
    if not arg or not _SHORT_ID_RE.match(arg):
        await message.reply(
            "Usage: `/anki <short_id>` — the 8-char ID shown under each note.",
            parse_mode="Markdown",
        )
        return

    note_id = await _resolve_note(api, tg_user_id, arg)
    if note_id is None:
        await message.reply("Couldn't find a note with that short ID.")
        return

    placeholder = await message.reply("🎴 Generating cards…")
    try:
        result = await api.generate_anki(tg_user_id, note_id)
    except Exception:
        log.exception("anki.api_failed", tg_user_id=tg_user_id, note_id=str(note_id))
        await placeholder.edit_text("❌ Couldn't generate cards.")
        return

    await placeholder.edit_text(
        _format_cards(result.get("cards", [])),
        parse_mode=None,
    )


@router.callback_query(F.data.startswith("note:anki:"))
async def anki_callback(
    cb: CallbackQuery,
    api: ApiClient,
    tg_user_id: int,
) -> None:
    if cb.data is None:
        return
    try:
        note_id = UUID(cb.data.split(":", 2)[2])
    except (IndexError, ValueError):
        await cb.answer("Bad payload", show_alert=False)
        return
    await cb.answer("Generating cards…")

    try:
        result = await api.generate_anki(tg_user_id, note_id)
    except Exception:
        log.exception("anki.cb.api_failed", tg_user_id=tg_user_id, note_id=str(note_id))
        if cb.message is not None:
            await cb.message.answer("❌ Couldn't generate cards.")
        return

    if cb.message is not None:
        await cb.message.answer(_format_cards(result.get("cards", [])))


async def _resolve_note(
    api: ApiClient, tg_user_id: int, short_id: str
) -> UUID | None:
    """List recent notes and look up the one matching `short_id`.

    Falls back through the API to avoid storing a separate short_id→uuid
    mapping. 100 most-recent should cover any realistic /anki workflow.
    """
    try:
        notes = await api._request(  # noqa: SLF001 (small helper, ok)
            tg_user_id, "GET", "/v1/notes?limit=100"
        )
    except Exception:
        log.exception("anki.list_notes.failed", tg_user_id=tg_user_id)
        return None
    if not isinstance(notes, list):
        return None
    for n in notes:
        if isinstance(n, dict) and str(n.get("id", ""))[:8] == short_id:
            return UUID(n["id"])
    return None


def _format_cards(cards: list[dict[str, Any]]) -> str:
    if not cards:
        return "No cards generated — the note may be too short or non-factual."
    lines: list[str] = [f"🎴 *{len(cards)} cards*\n"]
    for i, card in enumerate(cards, start=1):
        kind = (card.get("type") or "basic").lower()
        if kind == "cloze":
            lines.append(f"{i}. (cloze) {card.get('text', '')}")
        else:
            lines.append(
                f"{i}. Q: {card.get('front', '')}\n"
                f"   A: {card.get('back', '')}"
            )
    body = "\n\n".join(lines)
    return body[:4_000]


# Re-export the select symbol so a future feature (filtering by content
# fingerprint) can pick it up without re-importing.
_ = select
