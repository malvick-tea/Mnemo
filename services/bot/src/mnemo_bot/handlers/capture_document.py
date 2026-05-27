"""Document capture stub (milestone-2)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message

router = Router(name="capture_document")


@router.message(F.document)
async def capture_document(message: Message) -> None:
    # TODO(milestone-2): handler will POST /v1/capture/document; n8n
    # workflow 004-document-parse handles PDF/DOCX/EPUB/MD branching.
    await message.reply(
        "📄 Document capture is coming next. For now, paste the text directly."
    )
