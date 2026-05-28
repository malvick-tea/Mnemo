"""Document capture: PDF/DOCX/EPUB/MD/TXT attachments.

Files larger than `MNEMO_MAX_UPLOAD_MB` are rejected at the API edge — we
let the API decide rather than re-checking here, so the policy lives in
one place.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message
from redis.asyncio import Redis

from mnemo_bot.api_client import ApiClient
from mnemo_bot.logging import get_logger

log = get_logger(__name__)
router = Router(name="capture_document")

_PLACEHOLDER_TTL = 60 * 30

# Match by extension as a fallback when Telegram doesn't set mime_type.
_KNOWN_EXTS = (".pdf", ".docx", ".epub", ".md", ".markdown", ".txt")


@router.message(F.document)
async def capture_document(
    message: Message,
    api: ApiClient,
    redis: Redis,
    tg_user_id: int,
) -> None:
    doc = message.document
    if doc is None:
        return

    filename = doc.file_name or "document"
    mime = doc.mime_type or "application/octet-stream"
    if not _looks_supported(filename, mime):
        await message.reply(
            "❌ Unsupported document type. Send PDF, DOCX, EPUB, Markdown, or TXT."
        )
        return

    placeholder = await message.reply("📄 Parsing the document…")

    file_info = await message.bot.get_file(doc.file_id)  # type: ignore[union-attr]
    buf = await message.bot.download_file(file_info.file_path)  # type: ignore[union-attr,arg-type]
    if buf is None:
        await placeholder.edit_text("❌ Couldn't download the file.")
        return

    body = buf.read()
    try:
        result = await api.capture_document(tg_user_id, body, filename, mime)
    except Exception:
        log.exception("capture_document.api_failed", tg_user_id=tg_user_id)
        await placeholder.edit_text("❌ Couldn't queue that document.")
        return

    note_id = result["note_id"]
    await redis.set(
        f"mnemo:msg:{note_id}",
        f"{placeholder.chat.id}:{placeholder.message_id}",
        ex=_PLACEHOLDER_TTL,
    )
    log.info(
        "capture_document.queued",
        note_id=note_id, filename=filename, mime=mime, bytes=len(body),
    )


def _looks_supported(filename: str, mime: str) -> bool:
    name = (filename or "").lower()
    if name.endswith(_KNOWN_EXTS):
        return True
    return mime in {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/epub+zip",
        "text/plain",
        "text/markdown",
    }
