"""/digest — request the daily digest on demand."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from mnemo_bot.api_client import ApiClient
from mnemo_bot.logging import get_logger

router = Router(name="digest")
log = get_logger(__name__)


@router.message(Command("digest"))
async def digest_command(message: Message, api: ApiClient, tg_user_id: int) -> None:
    placeholder = await message.reply("🪶 Brewing today's digest…")
    try:
        result = await api.digest_today(tg_user_id)
    except Exception:
        log.exception("digest.failed")
        await placeholder.edit_text("❌ Couldn't generate the digest.")
        return
    text = result.get("text", "").strip() or "Nothing to digest yet — capture something first."
    await placeholder.edit_text(text[:4_000])
