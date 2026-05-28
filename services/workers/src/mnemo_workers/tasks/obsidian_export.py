"""Periodic Obsidian export.

Cron-driven actor. For every user with an active Obsidian integration:
1. Resolve the on-disk vault path from the integration config (decrypted).
2. List ready notes updated since `Integration.last_synced_at`.
3. Write each as a markdown file with YAML frontmatter.
4. Bump `last_synced_at` on success.

The vault path must be mounted into the workers container as a volume —
the default in .env.example is `/data/obsidian/<user_id>`.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import dramatiq
from mnemo_api.crypto import decrypt
from mnemo_api.db import session_factory
from mnemo_api.logging import get_logger
from mnemo_api.models import Integration, Note, NoteStatus, NoteTag, Tag
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo_workers.runner import run

log = get_logger(__name__)

_DEFAULT_VAULT_ROOT = "/data/obsidian"
_FILENAME_SAFE_RE = re.compile(r"[^\w\-]+", re.UNICODE)


@dramatiq.actor(queue_name="periodic", max_retries=1, time_limit=600_000)
def run_obsidian_export_for_all_users() -> None:
    run(_run_for_all)


async def _run_for_all() -> None:
    async with session_factory()() as session:
        rows = await session.execute(
            select(Integration).where(
                Integration.kind == "obsidian",
                Integration.is_active.is_(True),
            )
        )
        integrations = list(rows.scalars())

    for integ in integrations:
        try:
            await _export_user(integ.user_id, integ.id)
        except Exception:
            log.exception("obsidian.export.user_failed", user_id=str(integ.user_id))


async def _export_user(user_id: UUID, integration_id: UUID) -> None:
    async with session_factory()() as session:
        integ = await session.get(Integration, integration_id)
        if integ is None or not integ.is_active:
            return
        try:
            config = json.loads(decrypt(integ.config_encrypted).decode("utf-8"))
        except Exception as exc:
            log.warning(
                "obsidian.export.bad_credentials",
                user_id=str(user_id),
                error=str(exc),
            )
            return

        vault_root = Path(config.get("vault_path") or f"{_DEFAULT_VAULT_ROOT}/{user_id}")
        try:
            vault_root.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            log.warning(
                "obsidian.export.vault_unavailable",
                user_id=str(user_id),
                vault=str(vault_root),
                error=str(exc),
            )
            return

        since = integ.last_synced_at or datetime(1970, 1, 1, tzinfo=UTC)
        notes = await _select_notes(session, user_id, since)

        written = 0
        for note in notes:
            tags = await _tags_for(session, note.id)
            try:
                _write_markdown(vault_root, note, tags)
                written += 1
            except Exception:
                log.exception(
                    "obsidian.export.write_failed",
                    user_id=str(user_id),
                    note_id=str(note.id),
                )

        integ.last_synced_at = datetime.now(UTC)
        await session.commit()
        log.info(
            "obsidian.export.user_done",
            user_id=str(user_id),
            vault=str(vault_root),
            candidates=len(notes),
            written=written,
        )


async def _select_notes(session: AsyncSession, user_id: UUID, since: datetime) -> list[Note]:
    rows = await session.execute(
        select(Note)
        .where(
            Note.user_id == user_id,
            Note.status == NoteStatus.ready.value,
            Note.created_at >= since,
        )
        .order_by(Note.created_at)
        .limit(200)
    )
    return list(rows.scalars())


async def _tags_for(session: AsyncSession, note_id: UUID) -> list[str]:
    rows = await session.execute(
        select(Tag.name).join(NoteTag, NoteTag.tag_id == Tag.id).where(NoteTag.note_id == note_id)
    )
    return [r.name for r in rows]


def _write_markdown(vault_root: Path, note: Note, tags: list[str]) -> None:
    filename = _safe_filename(note)
    target = vault_root / filename
    body = _render_markdown(note, tags)
    # Atomic write: tmp + rename so partial files never appear in the vault.
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(body, encoding="utf-8")
    tmp.replace(target)


def _safe_filename(note: Note) -> str:
    title = (note.title or "untitled").strip()[:80]
    slug = _FILENAME_SAFE_RE.sub("-", title).strip("-") or "untitled"
    return f"{note.created_at:%Y-%m-%d}-{slug}-{str(note.id)[:8]}.md"


def _render_markdown(note: Note, tags: list[str]) -> str:
    front: list[str] = ["---"]
    front.append(f"id: {note.id}")
    if note.title:
        front.append(f"title: {json.dumps(note.title, ensure_ascii=False)}")
    front.append(f"captured: {note.captured_at.isoformat()}")
    front.append(f"source_type: {note.source_type}")
    if note.source_url:
        front.append(f"source_url: {note.source_url}")
    if tags:
        front.append(f"tags: [{', '.join(json.dumps(t) for t in tags)}]")
    front.append("---")

    parts = ["\n".join(front), ""]
    if note.summary:
        parts.append(f"> {note.summary}\n")
    parts.append(note.processed_content or note.raw_content or "")
    return "\n".join(parts).rstrip() + "\n"
