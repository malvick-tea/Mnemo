"""Document capture pipeline.

Triggered by the API after a multipart document upload lands in MinIO:
1. Download the document blob.
2. Branch on filename extension:
     .pdf            → pypdf text extraction
     .docx           → python-docx paragraph walk
     .epub           → ebooklib chapters → HTML strip
     .md / .markdown → decode + markdown → plaintext
     .txt            → decode as UTF-8 with replace
3. Persist extracted text as `processed_content`.
4. Hand off to `process_text_note` for summarize/tag/chunk/embed/publish.
"""

from __future__ import annotations

import io
import re
from uuid import UUID

import dramatiq
from mnemo_api.db import session_factory
from mnemo_api.logging import get_logger
from mnemo_api.models import Note, NoteStatus
from mnemo_api.services.queue import enqueue
from sqlalchemy import select

from mnemo_workers.minio_io import download_blob
from mnemo_workers.redis_io import get_redis
from mnemo_workers.runner import run

log = get_logger(__name__)


@dramatiq.actor(queue_name="default", max_retries=3, time_limit=300_000)
def process_document_note(note_id: str, blob_key: str, filename: str) -> None:
    run(_process_document_note, UUID(note_id), blob_key, filename)


async def _process_document_note(note_id: UUID, blob_key: str, filename: str) -> None:
    redis = get_redis()
    try:
        async with session_factory()() as session:
            note = (
                await session.execute(select(Note).where(Note.id == note_id))
            ).scalar_one_or_none()
            if note is None:
                log.warning("document.missing", note_id=str(note_id))
                return
            note.status = NoteStatus.processing.value
            await session.commit()

        try:
            blob = download_blob(blob_key)
        except Exception as exc:
            log.exception("document.download.failed", note_id=str(note_id))
            await _fail(note_id, f"download: {exc}")
            return

        try:
            text, doc_kind = _extract(blob, filename)
        except UnsupportedDocumentError as exc:
            await _fail(note_id, str(exc))
            return
        except Exception as exc:
            log.exception("document.parse.failed", note_id=str(note_id), filename=filename)
            await _fail(note_id, f"parse: {exc}")
            return

        text = _normalize_whitespace(text)
        if not text.strip():
            await _fail(note_id, "Document parsed to empty text")
            return

        async with session_factory()() as session:
            note = (
                await session.execute(select(Note).where(Note.id == note_id))
            ).scalar_one_or_none()
            if note is None:
                return
            note.processed_content = text
            meta = dict(note.source_metadata or {})
            meta["document"] = {"kind": doc_kind, "chars": len(text)}
            note.source_metadata = meta
            if not note.title:
                note.title = filename
            await session.commit()

        await enqueue(redis, "process_text_note", {"note_id": str(note_id)})
        log.info(
            "document.parsed",
            note_id=str(note_id),
            kind=doc_kind,
            chars=len(text),
        )
    finally:
        await redis.aclose()


class UnsupportedDocumentError(Exception):
    pass


_KIND_BY_EXT = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".epub": "epub",
    ".md": "markdown",
    ".markdown": "markdown",
    ".txt": "text",
}


def _extract(blob: bytes, filename: str) -> tuple[str, str]:
    name = filename.lower()
    kind = next(
        (kind for ext, kind in _KIND_BY_EXT.items() if name.endswith(ext)),
        None,
    )
    if kind is None:
        raise UnsupportedDocumentError(
            f"Unsupported document extension: {filename!r}. " "Supported: .pdf .docx .epub .md .txt"
        )

    if kind == "pdf":
        return _extract_pdf(blob), kind
    if kind == "docx":
        return _extract_docx(blob), kind
    if kind == "epub":
        return _extract_epub(blob), kind
    if kind == "markdown":
        return _extract_markdown(blob), kind
    # text
    return blob.decode("utf-8", errors="replace"), kind


def _extract_pdf(blob: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(blob))
    parts: list[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            parts.append("")
    return "\n\n".join(p for p in parts if p.strip())


def _extract_docx(blob: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(blob))
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _extract_epub(blob: bytes) -> str:
    # ebooklib needs a path-like; use a BytesIO via its `epub.read_epub`
    # workaround through a temp file for compatibility across versions.
    import tempfile

    from bs4 import BeautifulSoup
    from ebooklib import ITEM_DOCUMENT, epub

    with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as tmp:
        tmp.write(blob)
        path = tmp.name
    try:
        book = epub.read_epub(path)
        chapters: list[str] = []
        for item in book.get_items_of_type(ITEM_DOCUMENT):
            soup = BeautifulSoup(item.get_content(), "html.parser")
            text = soup.get_text(separator="\n").strip()
            if text:
                chapters.append(text)
        return "\n\n".join(chapters)
    finally:
        import os

        os.unlink(path)


def _extract_markdown(blob: bytes) -> str:
    import markdown
    from bs4 import BeautifulSoup

    md_text = blob.decode("utf-8", errors="replace")
    html = markdown.markdown(md_text, extensions=["fenced_code", "tables"])
    return str(BeautifulSoup(html, "html.parser").get_text(separator="\n").strip())


_WS_RE = re.compile(r"[ \t]+")
_NL_RE = re.compile(r"\n{3,}")


def _normalize_whitespace(text: str) -> str:
    text = _WS_RE.sub(" ", text)
    text = _NL_RE.sub("\n\n", text)
    return text.strip()


async def _fail(note_id: UUID, message: str) -> None:
    async with session_factory()() as session:
        note = (await session.execute(select(Note).where(Note.id == note_id))).scalar_one_or_none()
        if note is None:
            return
        note.status = NoteStatus.failed.value
        note.error_message = message[:2_000]
        await session.commit()
