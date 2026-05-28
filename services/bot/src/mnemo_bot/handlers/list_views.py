"""Read-only commands: ``/recent``, ``/tags``, ``/export``.

These three were documented in ``/help`` from the start; this file is the
first concrete implementation. Export is intentionally a stub for now —
streaming a multi-GB zip back through Telegram is a milestone-3 problem.
"""

from __future__ import annotations

from typing import Any

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from mnemo_bot.api_client import ApiClient
from mnemo_bot.logging import get_logger

router = Router(name="list_views")
log = get_logger(__name__)

_RECENT_LIMIT = 10
_TAG_LIMIT = 30


@router.message(Command("recent"))
async def recent_command(
    message: Message, api: ApiClient, tg_user_id: int
) -> None:
    placeholder = await message.reply("📂 Pulling your last captures…")
    try:
        notes = await api._request(  # noqa: SLF001 — small helper, narrow use
            tg_user_id, "GET", f"/v1/notes?limit={_RECENT_LIMIT}"
        )
    except Exception:
        log.exception("recent.api_failed", tg_user_id=tg_user_id)
        await placeholder.edit_text("❌ Couldn't reach Mnemo.")
        return

    if not isinstance(notes, list) or not notes:
        await placeholder.edit_text(
            "Nothing yet — send me something to capture."
        )
        return

    lines: list[str] = ["🗂 *Recent captures*\n"]
    for n in notes:
        if not isinstance(n, dict):
            continue
        short = str(n.get("id", ""))[:8]
        title = n.get("title") or "(untitled)"
        kind = n.get("source_type", "?")
        when = (n.get("created_at") or "")[:10]
        lines.append(f"`[{short}]` {kind} · {when} — {title}")
    await placeholder.edit_text(
        "\n".join(lines)[:4_000], parse_mode="Markdown",
    )


@router.message(Command("tags"))
async def tags_command(
    message: Message, api: ApiClient, tg_user_id: int
) -> None:
    placeholder = await message.reply("🏷 Loading tags…")
    try:
        tags = await api._request(  # noqa: SLF001
            tg_user_id, "GET", "/v1/tags"
        )
    except Exception:
        log.exception("tags.api_failed", tg_user_id=tg_user_id)
        await placeholder.edit_text("❌ Couldn't load tags.")
        return

    if not isinstance(tags, list) or not tags:
        await placeholder.edit_text(
            "No tags yet — tags are assigned automatically when notes finish processing."
        )
        return

    lines = ["🏷 *Tags*\n"]
    for t in _format_tags(tags)[:_TAG_LIMIT]:
        lines.append(t)
    await placeholder.edit_text(
        "\n".join(lines)[:4_000], parse_mode="Markdown",
    )


@router.message(Command("export"))
async def export_command(message: Message) -> None:
    # TODO(milestone-3): stream a zip of {notes JSON + originals from MinIO}
    # via Telegram file upload. Hold off until we have backpressure handling
    # for >50 MB exports.
    await message.reply(
        "📦 Bulk export is on the milestone-3 list.\n\n"
        "Until then, use `scripts/backup.sh` on the host to snapshot "
        "Postgres + Qdrant + MinIO into `./backups/`.",
        parse_mode="Markdown",
    )


def _format_tags(tags: list[Any]) -> list[str]:
    rows: list[tuple[str, int]] = []
    for t in tags:
        if not isinstance(t, dict):
            continue
        name = t.get("name", "?")
        count = int(t.get("count") or 0)
        rows.append((name, count))
    rows.sort(key=lambda kv: kv[1], reverse=True)
    return [f"`#{name}` · {count}" for name, count in rows]
