"""Photo capture stub (milestone-2)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message

router = Router(name="capture_photo")


@router.message(F.photo)
async def capture_photo(message: Message) -> None:
    # TODO(milestone-2): wire to /v1/capture/photo when n8n workflow 003 is live.
    await message.reply(
        "📷 Photo capture is coming in the next milestone. "
        "For now, send the text content directly."
    )
