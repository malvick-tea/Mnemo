"""Forwarded message capture.

A forwarded text message is captured as a text note with extra provenance
metadata (origin chat/user, forward date). Forwards of media (photo/voice/
document) are not handled here — Telegram routes those through the type-
specific handlers; we drop the `forward_*` filter so we don't double-fire.
"""

from __future__ import annotations

from typing import Any

from aiogram import F, Router
from aiogram.types import Message
from redis.asyncio import Redis

from mnemo_bot.api_client import ApiClient
from mnemo_bot.keyboards import note_actions
from mnemo_bot.logging import get_logger

log = get_logger(__name__)
router = Router(name="capture_forward")

_PLACEHOLDER_TTL = 60 * 30


@router.message(
    (F.forward_from | F.forward_from_chat | F.forward_origin)
    & F.text
    & ~F.photo
    & ~F.voice
    & ~F.audio
    & ~F.document
)
async def capture_forward(
    message: Message,
    api: ApiClient,
    redis: Redis,
    tg_user_id: int,
) -> None:
    text = message.text or message.caption or ""
    if not text.strip():
        await message.reply("↪️ Forward had no text. Forward a message with text content.")
        return

    placeholder = await message.reply("↪️ Saving forwarded message…")
    forward_meta = _extract_forward_metadata(message)

    try:
        result = await api.capture_forward(tg_user_id, text, forward_meta)
    except Exception:
        log.exception("capture_forward.api_failed", tg_user_id=tg_user_id)
        await placeholder.edit_text("❌ Couldn't queue the forward.")
        return

    note_id = result["note_id"]
    await placeholder.edit_text(
        "✅ Saved. Tagging and embedding in the background…",
        reply_markup=note_actions(note_id),
    )
    await redis.set(
        f"mnemo:msg:{note_id}",
        f"{placeholder.chat.id}:{placeholder.message_id}",
        ex=_PLACEHOLDER_TTL,
    )
    log.info(
        "capture_forward.queued",
        note_id=note_id,
        origin_type=forward_meta.get("origin_type"),
    )


def _extract_forward_metadata(message: Message) -> dict[str, Any]:
    """Build a Pydantic-compatible ForwardMetadata dict from an aiogram Message.

    Handles both the legacy `forward_from`/`forward_from_chat` fields and
    the newer `forward_origin` union (Telegram Bot API 7.0+).
    """
    meta: dict[str, Any] = {}

    origin = getattr(message, "forward_origin", None)
    if origin is not None:
        kind = getattr(origin, "type", None)
        if kind == "user":
            meta["origin_type"] = "user"
            sender = getattr(origin, "sender_user", None)
            if sender is not None:
                meta["from_user_id"] = sender.id
                meta["from_user_name"] = _full_name(sender)
        elif kind == "hidden_user":
            meta["origin_type"] = "hidden_user"
            meta["from_user_name"] = getattr(origin, "sender_user_name", None)
        elif kind == "chat":
            meta["origin_type"] = "chat"
            chat = getattr(origin, "sender_chat", None)
            if chat is not None:
                meta["from_chat_id"] = chat.id
                meta["from_chat_title"] = chat.title
                meta["from_chat_username"] = chat.username
        elif kind == "channel":
            meta["origin_type"] = "channel"
            chat = getattr(origin, "chat", None)
            if chat is not None:
                meta["from_chat_id"] = chat.id
                meta["from_chat_title"] = chat.title
                meta["from_chat_username"] = chat.username
            meta["message_id"] = getattr(origin, "message_id", None)
        date = getattr(origin, "date", None)
        if date is not None:
            meta["forward_date"] = date.isoformat() if hasattr(date, "isoformat") else None

    if message.forward_from is not None and "from_user_id" not in meta:
        meta.setdefault("origin_type", "user")
        meta["from_user_id"] = message.forward_from.id
        meta["from_user_name"] = _full_name(message.forward_from)
    if message.forward_from_chat is not None and "from_chat_id" not in meta:
        meta.setdefault("origin_type", "channel")
        meta["from_chat_id"] = message.forward_from_chat.id
        meta["from_chat_title"] = message.forward_from_chat.title
        meta["from_chat_username"] = message.forward_from_chat.username

    return {k: v for k, v in meta.items() if v is not None}


def _full_name(user: Any) -> str:
    parts = [getattr(user, "first_name", None), getattr(user, "last_name", None)]
    return " ".join(p for p in parts if p) or (getattr(user, "username", None) or "")
