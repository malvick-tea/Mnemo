"""Inline note-action callbacks: view tags, edit, delete.

The 🎴 Anki button is handled in ``handlers.anki``. The 🏷 Tags / 📝 Edit /
🗑 Delete buttons are advertised on every note message; previously they had no
handler, so tapping them did nothing. They're wired here to the existing
notes API.
"""

from __future__ import annotations

from uuid import UUID

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from mnemo_bot.api_client import ApiClient
from mnemo_bot.logging import get_logger
from mnemo_bot.states import NoteEditFlow

router = Router(name="note_actions")
log = get_logger(__name__)


def _note_id(data: str | None) -> UUID | None:
    try:
        return UUID((data or "").split(":", 2)[2])
    except (IndexError, ValueError):
        return None


@router.callback_query(F.data.startswith("note:tags:"))
async def show_tags(cq: CallbackQuery, api: ApiClient, tg_user_id: int) -> None:
    note_id = _note_id(cq.data)
    if note_id is None:
        await cq.answer("Bad payload")
        return
    try:
        note = await api.get_note(tg_user_id, note_id)
    except Exception:
        log.exception("note.tags.fetch_failed", note_id=str(note_id))
        await cq.answer("Couldn't load tags.", show_alert=True)
        return
    tags = note.get("tags") or []
    if tags:
        names = ", ".join(f"#{t['name']}" for t in tags)
        await cq.answer(f"Tags: {names}"[:200], show_alert=True)
    else:
        await cq.answer("No tags yet — they're added as the note is processed.", show_alert=True)


@router.callback_query(F.data.startswith("note:delete:"))
async def delete_note_cb(cq: CallbackQuery, api: ApiClient, tg_user_id: int) -> None:
    note_id = _note_id(cq.data)
    if note_id is None:
        await cq.answer("Bad payload")
        return
    try:
        await api.delete_note(tg_user_id, note_id)
    except Exception:
        log.exception("note.delete.failed", note_id=str(note_id))
        await cq.answer("Couldn't delete the note.", show_alert=True)
        return
    await cq.answer("Deleted.")
    if cq.message is not None:
        try:
            await cq.message.answer("🗑 Note deleted.")
        except Exception:
            log.debug("note.delete.notify_failed", note_id=str(note_id))


@router.callback_query(F.data.startswith("note:edit:"))
async def edit_note_cb(cq: CallbackQuery, state: FSMContext, tg_user_id: int) -> None:
    note_id = _note_id(cq.data)
    if note_id is None:
        await cq.answer("Bad payload")
        return
    await state.set_state(NoteEditFlow.awaiting_text)
    await state.update_data(edit_note_id=str(note_id))
    await cq.answer()
    if cq.message is not None:
        await cq.message.reply("✏️ Send the new text for this note, or /cancel.")


@router.message(NoteEditFlow.awaiting_text, F.text == "/cancel")
async def cancel_edit(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.reply("Edit cancelled.")


@router.message(NoteEditFlow.awaiting_text, F.text & ~F.text.startswith("/"))
async def apply_edit(message: Message, state: FSMContext, api: ApiClient, tg_user_id: int) -> None:
    data = await state.get_data()
    note_id_str = data.get("edit_note_id")
    await state.clear()
    if not note_id_str:
        return
    new_text = (message.text or "").strip()
    if not new_text:
        await message.reply("Nothing to update.")
        return
    try:
        await api.update_note(tg_user_id, UUID(note_id_str), processed_content=new_text)
    except Exception:
        log.exception("note.edit.failed", note_id=note_id_str)
        await message.reply("❌ Couldn't update the note.")
        return
    await message.reply("✅ Note updated.")
