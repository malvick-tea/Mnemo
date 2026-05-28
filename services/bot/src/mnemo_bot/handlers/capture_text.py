"""Text capture: any non-command text message (or `/save <text>`).

The bot:
1. Captures to the API immediately (returns within ~1s in the happy path).
2. Stores `note_id → tg_message_id` in Redis so the note-ready subscriber
   can edit this reply once processing finishes.
"""

from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from redis.asyncio import Redis

from mnemo_bot.api_client import ApiClient
from mnemo_bot.keyboards import note_actions
from mnemo_bot.logging import get_logger

log = get_logger(__name__)
router = Router(name="capture_text")

_URL_RE = re.compile(r"https?://\S+")
_PLACEHOLDER_TTL = 60 * 30  # 30 min


def _has_url(text: str) -> bool:
    return bool(_URL_RE.search(text))


@router.message(Command("save"))
async def save_command(
    message: Message,
    command: CommandObject,
    api: ApiClient,
    redis: Redis,
    tg_user_id: int,
) -> None:
    text = command.args or ""
    if not text.strip():
        await message.reply("Usage: /save your text here")
        return
    await _capture(message, api, redis, tg_user_id, text)


@router.message(F.text & ~F.text.startswith("/"))
async def autocapture_text(
    message: Message,
    api: ApiClient,
    redis: Redis,
    tg_user_id: int,
) -> None:
    text = message.text or ""

    # If the text is *only* a URL, delegate to URL capture (handled in
    # `capture_url.py`) — but that handler runs after this one due to
    # registration order. We early-return to let it pick this up.
    if _URL_RE.fullmatch(text.strip()):
        return

    await _capture(message, api, redis, tg_user_id, text)


async def _capture(
    message: Message,
    api: ApiClient,
    redis: Redis,
    tg_user_id: int,
    text: str,
) -> None:
    placeholder = await message.reply("📝 Saving…")
    try:
        result = await api.capture_text(tg_user_id, text)
    except Exception:
        log.exception("capture_text.api_failed", tg_user_id=tg_user_id)
        await placeholder.edit_text("❌ Couldn't reach Mnemo. Try again in a moment.")
        return

    note_id = result["note_id"]
    await placeholder.edit_text(
        "✅ Saved. Tagging and embedding in the background…",
        reply_markup=note_actions(note_id),
    )
    # Map note_id → (chat_id, message_id) so the note-ready listener can
    # edit this message once processing completes.
    await redis.set(
        f"mnemo:msg:{note_id}",
        f"{placeholder.chat.id}:{placeholder.message_id}",
        ex=_PLACEHOLDER_TTL,
    )
    log.info("capture_text.ok", note_id=note_id)
