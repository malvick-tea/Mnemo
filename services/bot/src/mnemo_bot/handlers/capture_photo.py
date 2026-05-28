"""Photo capture: any message containing one or more photo sizes.

Telegram delivers photos as a list of `PhotoSize`s (thumb → original).
We pick the largest by `(width * height)` for the best OCR/description.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message
from redis.asyncio import Redis

from mnemo_bot.api_client import ApiClient
from mnemo_bot.logging import get_logger

log = get_logger(__name__)
router = Router(name="capture_photo")

_PLACEHOLDER_TTL = 60 * 30


@router.message(F.photo)
async def capture_photo(
    message: Message,
    api: ApiClient,
    redis: Redis,
    tg_user_id: int,
) -> None:
    if not message.photo:
        return
    placeholder = await message.reply("📷 Reading the image…")

    largest = max(message.photo, key=lambda p: p.width * p.height)
    file_info = await message.bot.get_file(largest.file_id)  # type: ignore[union-attr]
    buf = await message.bot.download_file(file_info.file_path)  # type: ignore[union-attr,arg-type]
    if buf is None:
        await placeholder.edit_text("❌ Couldn't download the photo.")
        return

    body = buf.read()
    filename = f"photo-{largest.file_unique_id}.jpg"
    mime = "image/jpeg"
    caption = (message.caption or "").strip() or None

    try:
        result = await api.capture_photo(
            tg_user_id, body, filename, mime, caption=caption
        )
    except Exception:
        log.exception("capture_photo.api_failed", tg_user_id=tg_user_id)
        await placeholder.edit_text("❌ Couldn't queue that photo.")
        return

    note_id = result["note_id"]
    await redis.set(
        f"mnemo:msg:{note_id}",
        f"{placeholder.chat.id}:{placeholder.message_id}",
        ex=_PLACEHOLDER_TTL,
    )
    log.info(
        "capture_photo.queued",
        note_id=note_id, bytes=len(body), w=largest.width, h=largest.height,
    )
