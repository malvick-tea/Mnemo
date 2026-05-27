"""Background task: subscribe to Redis `note.ready.*` and edit placeholders.

For each ready note we look up the placeholder message we stored at capture
time (`mnemo:msg:<note_id>` → `<chat_id>:<message_id>`) and edit it with
the final summary + tags.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from uuid import UUID

from aiogram import Bot
from redis.asyncio import Redis

from mnemo_bot.api_client import ApiClient
from mnemo_bot.keyboards import note_actions
from mnemo_bot.logging import get_logger

log = get_logger(__name__)


async def listen_note_ready(bot: Bot, redis: Redis, api: ApiClient) -> None:
    pubsub = redis.pubsub(ignore_subscribe_messages=True)
    # Subscribe to every user's channel via pattern.
    await pubsub.psubscribe("note.ready.*")
    log.info("note_ready.listener.start")
    try:
        async for msg in pubsub.listen():
            try:
                await _handle(bot, redis, api, msg)
            except Exception:  # noqa: BLE001
                log.exception("note_ready.handle_failed", msg=str(msg)[:200])
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.aclose()
        log.info("note_ready.listener.stop")


async def _handle(
    bot: Bot, redis: Redis, api: ApiClient, msg: dict[str, Any]
) -> None:
    if msg.get("type") != "pmessage":
        return
    data = json.loads(msg["data"])
    note_id_str = data["note_id"]
    user_id_str = data["user_id"]
    note_id = UUID(note_id_str)

    placeholder = await redis.get(f"mnemo:msg:{note_id_str}")
    if placeholder is None:
        return
    chat_id_str, message_id_str = placeholder.decode("utf-8").split(":")

    # `note_ready_listener` doesn't know which TG ID owns the note — we
    # resolve by reading from the user record via a service request that
    # uses a privileged token. For v1 we ask the API for the note using
    # the user's own JWT; the API filters by user_id internally.
    # We map user_id → tg_user_id via a small Redis hash maintained on
    # capture: `mnemo:user:<api_user_id>` = tg_user_id.
    tg_user_id_raw = await redis.get(f"mnemo:user:{user_id_str}")
    if tg_user_id_raw is None:
        log.warning("note_ready.no_tg_mapping", user_id=user_id_str)
        return
    tg_user_id = int(tg_user_id_raw)

    try:
        note = await api.get_note(tg_user_id, note_id)
    except Exception:
        log.exception("note_ready.fetch_failed", note_id=note_id_str)
        return

    text = _format_note(note)
    try:
        await bot.edit_message_text(
            text=text[:4_000],
            chat_id=int(chat_id_str),
            message_id=int(message_id_str),
            reply_markup=note_actions(note_id),
            parse_mode="Markdown",
        )
        await redis.delete(f"mnemo:msg:{note_id_str}")
    except Exception:  # noqa: BLE001
        log.exception("note_ready.edit_failed", note_id=note_id_str)


def _format_note(note: dict[str, Any]) -> str:
    title = note.get("title") or "(untitled)"
    summary = note.get("summary") or note.get("processed_content") or ""
    tags = note.get("tags") or []
    tag_line = " ".join(f"#{t['name']}" for t in tags) if tags else ""
    out = f"✅ *{title}*\n\n{summary}"
    if tag_line:
        out += f"\n\n{tag_line}"
    return out
