"""Voice capture: voice notes + audio messages.

Downloads the file from Telegram CDN and POSTs multipart to the API.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message
from redis.asyncio import Redis

from mnemo_bot.api_client import ApiClient
from mnemo_bot.logging import get_logger

log = get_logger(__name__)
router = Router(name="capture_voice")

_PLACEHOLDER_TTL = 60 * 30


@router.message(F.voice | F.audio)
async def capture_voice(
    message: Message,
    api: ApiClient,
    redis: Redis,
    tg_user_id: int,
) -> None:
    placeholder = await message.reply("🎙 Transcribing… this can take ~30 s.")

    file_obj = message.voice or message.audio
    if file_obj is None:
        await placeholder.edit_text("❌ No audio attached.")
        return

    file_info = await message.bot.get_file(file_obj.file_id)  # type: ignore[union-attr]
    buf = await message.bot.download_file(file_info.file_path)  # type: ignore[union-attr,arg-type]
    if buf is None:
        await placeholder.edit_text("❌ Couldn't download the voice file.")
        return

    body = buf.read()
    filename = getattr(file_obj, "file_name", None) or f"voice-{file_obj.file_id}.ogg"
    mime = getattr(file_obj, "mime_type", None) or "audio/ogg"

    try:
        result = await api.capture_voice(tg_user_id, body, filename, mime)
    except Exception:
        log.exception("capture_voice.api_failed", tg_user_id=tg_user_id)
        await placeholder.edit_text("❌ Couldn't queue that voice note.")
        return

    note_id = result["note_id"]
    await redis.set(
        f"mnemo:msg:{note_id}",
        f"{placeholder.chat.id}:{placeholder.message_id}",
        ex=_PLACEHOLDER_TTL,
    )
    log.info("capture_voice.queued", note_id=note_id, bytes=len(body))
