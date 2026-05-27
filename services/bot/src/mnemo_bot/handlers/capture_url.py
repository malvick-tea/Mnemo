"""URL capture: messages whose entire text is a URL."""

from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.types import Message
from redis.asyncio import Redis

from mnemo_bot.api_client import ApiClient
from mnemo_bot.logging import get_logger

log = get_logger(__name__)
router = Router(name="capture_url")

_URL_FULL = re.compile(r"^\s*https?://\S+\s*$")
_PLACEHOLDER_TTL = 60 * 30


@router.message(F.text.regexp(_URL_FULL))
async def capture_url(
    message: Message,
    api: ApiClient,
    redis: Redis,
    tg_user_id: int,
) -> None:
    url = (message.text or "").strip()
    placeholder = await message.reply("🔗 Fetching and summarizing…")
    try:
        result = await api.capture_url(tg_user_id, url)
    except Exception:
        log.exception("capture_url.api_failed", url=url)
        await placeholder.edit_text("❌ Couldn't queue that URL. Try again.")
        return

    note_id = result["note_id"]
    await redis.set(
        f"mnemo:msg:{note_id}",
        f"{placeholder.chat.id}:{placeholder.message_id}",
        ex=_PLACEHOLDER_TTL,
    )
    log.info("capture_url.queued", url=url, note_id=note_id)
