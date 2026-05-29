"""Background tasks: subscribe to Redis bot-facing channels.

Two pub/sub patterns are watched:

- ``note.ready.*`` — a note finished processing. We look up the placeholder
  message we stored at capture time and edit it with the final summary/tags.
- ``digest.daily.*`` — the daily digest scheduler enqueued a fresh digest
  for a user; we send it as a new Telegram message.

Both payloads include ``tg_user_id`` so we don't need a separate Redis
mapping or DB lookup.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from uuid import UUID

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from redis.asyncio import Redis

from mnemo_bot.api_client import ApiClient
from mnemo_bot.keyboards import note_actions
from mnemo_bot.logging import get_logger

log = get_logger(__name__)


async def listen_bot_events(bot: Bot, redis: Redis, api: ApiClient) -> None:
    """Subscribe to both note-ready and digest channels concurrently."""
    pubsub = redis.pubsub(ignore_subscribe_messages=True)
    await pubsub.psubscribe("note.ready.*", "digest.daily.*")
    log.info("bot_events.listener.start")
    try:
        async for msg in pubsub.listen():
            try:
                await _dispatch(bot, redis, api, msg)
            except Exception:
                log.exception("bot_events.handle_failed", msg=str(msg)[:200])
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.aclose()
        log.info("bot_events.listener.stop")


# Back-compat alias — `main.py` historically called `listen_note_ready`.
listen_note_ready = listen_bot_events


async def _dispatch(bot: Bot, redis: Redis, api: ApiClient, msg: dict[str, Any]) -> None:
    if msg.get("type") != "pmessage":
        return
    channel = (msg.get("channel") or b"").decode("utf-8", errors="replace")
    try:
        data = json.loads(msg["data"])
    except (json.JSONDecodeError, KeyError):
        log.warning("bot_events.bad_payload", channel=channel)
        return

    if channel.startswith("note.ready."):
        await _handle_note_ready(bot, redis, api, data)
    elif channel.startswith("digest.daily."):
        await _handle_digest(bot, data)
    else:
        log.warning("bot_events.unknown_channel", channel=channel)


async def _handle_note_ready(bot: Bot, redis: Redis, api: ApiClient, data: dict[str, Any]) -> None:
    note_id_str = data.get("note_id")
    tg_user_id = data.get("tg_user_id")
    if note_id_str is None or tg_user_id is None:
        log.warning("note_ready.incomplete_payload", payload=data)
        return

    note_id = UUID(note_id_str)
    placeholder = await redis.get(f"mnemo:msg:{note_id_str}")
    if placeholder is None:
        return
    try:
        chat_id_str, message_id_str = placeholder.decode("utf-8").split(":")
    except ValueError:
        log.warning("note_ready.bad_placeholder", value=placeholder[:50])
        return

    try:
        note = await api.get_note(int(tg_user_id), note_id)
    except Exception:
        log.exception("note_ready.fetch_failed", note_id=note_id_str)
        return

    status = note.get("status")
    text = _format_note(note)
    edited = False
    try:
        await bot.edit_message_text(
            text=_md_escape(text)[:4_000],
            chat_id=int(chat_id_str),
            message_id=int(message_id_str),
            reply_markup=note_actions(note_id),
            parse_mode="MarkdownV2",
        )
        edited = True
    except TelegramBadRequest:
        # Parse error or untouched message — retry plain.
        try:
            await bot.edit_message_text(
                text=text[:4_000],
                chat_id=int(chat_id_str),
                message_id=int(message_id_str),
                reply_markup=note_actions(note_id),
                parse_mode=None,
            )
            edited = True
        except Exception:
            log.exception("note_ready.edit_failed", note_id=note_id_str)
    except Exception:
        log.exception("note_ready.edit_failed", note_id=note_id_str)

    # Release the placeholder mapping only once the note is terminal and we
    # actually edited it — so an early/duplicate event can't orphan a note
    # that a later successful retry still needs to surface.
    if edited and status in ("ready", "failed"):
        await redis.delete(f"mnemo:msg:{note_id_str}")


async def _handle_digest(bot: Bot, data: dict[str, Any]) -> None:
    tg_user_id = data.get("tg_user_id")
    text = data.get("text") or ""
    if tg_user_id is None or not text.strip():
        log.warning("digest.incomplete_payload", payload=str(data)[:200])
        return
    try:
        await bot.send_message(
            chat_id=int(tg_user_id),
            text=f"📰 *Daily digest*\n\n{text}"[:4_000],
            parse_mode=None,
        )
        log.info("digest.delivered", tg_user_id=tg_user_id, len=len(text))
    except Exception:
        log.exception("digest.send_failed", tg_user_id=tg_user_id)


def _format_note(note: dict[str, Any]) -> str:
    status = note.get("status") or "ready"
    title = note.get("title") or "(untitled)"
    summary = note.get("summary") or note.get("processed_content") or ""
    tags = note.get("tags") or []
    tag_line = " ".join(f"#{t['name']}" for t in tags) if tags else ""

    if status == "failed":
        err = note.get("error_message") or "Unknown error."
        return f"❌ *{title}*\n\nProcessing failed: {err}"

    icon = "✅" if status == "ready" else "⏳"
    out = f"{icon} *{title}*\n\n{summary}"
    if tag_line:
        out += f"\n\n{tag_line}"
    return out


# MarkdownV2 reserved characters — Telegram requires escaping outside of
# explicit formatting. We keep `*` and `_` so titles/bold still work.
_MD_ESCAPE = {ch: f"\\{ch}" for ch in r"[]()~`>#+-=|{}.!"}


def _md_escape(text: str) -> str:
    return "".join(_MD_ESCAPE.get(ch, ch) for ch in text)
