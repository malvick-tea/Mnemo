"""Forwarded message capture stub (milestone-2)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message

router = Router(name="capture_forward")


@router.message(F.forward_from | F.forward_from_chat | F.forward_origin)
async def capture_forward(message: Message) -> None:
    # TODO(milestone-2): preserve forward_from metadata, hand off to /v1/capture/forward.
    await message.reply("↪️ Forwarded captures land in the next milestone.")
