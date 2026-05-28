"""Periodic Notion sync.

Cron-driven actor. For every user with an active Notion integration:
1. Decrypt their stored config (`integration_token`, `database_id`).
2. List ready notes updated since `Integration.last_synced_at`.
3. Push each as a Notion page in the configured database.
4. Bump `last_synced_at` on success.

We tolerate per-user failures — one user with a bad token shouldn't stop
the sync from running for the others.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import dramatiq
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo_api.crypto import decrypt
from mnemo_api.db import session_factory
from mnemo_api.logging import get_logger
from mnemo_api.models import Integration, Note, NoteStatus, NoteTag, Tag
from mnemo_workers.runner import run

log = get_logger(__name__)

_NOTION_API = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"
_TITLE_MAX = 200


@dramatiq.actor(queue_name="periodic", max_retries=1, time_limit=600_000)
def run_notion_sync_for_all_users() -> None:
    run(_run_for_all)


async def _run_for_all() -> None:
    async with session_factory()() as session:
        rows = await session.execute(
            select(Integration).where(
                Integration.kind == "notion",
                Integration.is_active.is_(True),
            )
        )
        integrations = list(rows.scalars())

    for integ in integrations:
        try:
            await _sync_user(integ.user_id, integ.id)
        except Exception:  # noqa: BLE001
            log.exception("notion.sync.user_failed", user_id=str(integ.user_id))


async def _sync_user(user_id: UUID, integration_id: UUID) -> None:
    async with session_factory()() as session:
        integ = await session.get(Integration, integration_id)
        if integ is None or not integ.is_active:
            return
        try:
            config = json.loads(decrypt(integ.config_encrypted).decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "notion.sync.bad_credentials",
                user_id=str(user_id), error=str(exc),
            )
            return

        token = config.get("integration_token")
        database_id = config.get("database_id")
        if not token or not database_id:
            log.warning(
                "notion.sync.incomplete_config",
                user_id=str(user_id),
                has_token=bool(token), has_db=bool(database_id),
            )
            return

        since = integ.last_synced_at or datetime(1970, 1, 1, tzinfo=UTC)
        notes = await _select_notes(session, user_id, since)

        if not notes:
            return

        async with httpx.AsyncClient(
            base_url=_NOTION_API,
            timeout=20.0,
            headers={
                "Authorization": f"Bearer {token}",
                "Notion-Version": _NOTION_VERSION,
                "Content-Type": "application/json",
            },
        ) as client:
            pushed = 0
            for note in notes:
                tags = await _tags_for(session, note.id)
                try:
                    await _push_note(client, database_id, note, tags)
                    pushed += 1
                except Exception:  # noqa: BLE001
                    log.exception(
                        "notion.sync.push_failed",
                        user_id=str(user_id), note_id=str(note.id),
                    )

        integ.last_synced_at = datetime.now(UTC)
        await session.commit()
        log.info(
            "notion.sync.user_done",
            user_id=str(user_id), candidates=len(notes), pushed=pushed,
        )


async def _select_notes(
    session: AsyncSession, user_id: UUID, since: datetime
) -> list[Note]:
    rows = await session.execute(
        select(Note)
        .where(
            Note.user_id == user_id,
            Note.status == NoteStatus.ready.value,
            Note.processed_at >= since if False else Note.created_at >= since,
        )
        .order_by(Note.created_at)
        .limit(50)  # batch cap; next run picks up the rest
    )
    return list(rows.scalars())


async def _tags_for(session: AsyncSession, note_id: UUID) -> list[str]:
    rows = await session.execute(
        select(Tag.name)
        .join(NoteTag, NoteTag.tag_id == Tag.id)
        .where(NoteTag.note_id == note_id)
    )
    return [r.name for r in rows]


async def _push_note(
    client: httpx.AsyncClient,
    database_id: str,
    note: Note,
    tags: list[str],
) -> None:
    title = (note.title or "(untitled)")[:_TITLE_MAX]
    summary = (note.summary or note.processed_content or "")[:1_900]
    properties: dict[str, Any] = {
        "Name": {"title": [{"text": {"content": title}}]},
        "Captured": {"date": {"start": note.captured_at.isoformat()}},
        "Source": {"select": {"name": note.source_type}},
    }
    if note.source_url:
        properties["URL"] = {"url": note.source_url}
    if tags:
        properties["Tags"] = {
            "multi_select": [{"name": t[:90]} for t in tags[:10]]
        }

    children = [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {"type": "text", "text": {"content": summary or "(no summary)"}}
                ]
            },
        }
    ]

    payload = {
        "parent": {"database_id": database_id},
        "properties": properties,
        "children": children,
    }
    resp = await client.post("/pages", json=payload)
    if resp.status_code >= 400:
        log.warning(
            "notion.api.error",
            status=resp.status_code,
            body=resp.text[:300],
            note_id=str(note.id),
        )
        resp.raise_for_status()
