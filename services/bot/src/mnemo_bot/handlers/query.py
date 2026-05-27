"""Query / RAG handler.

Two entry points:
- `/q <question>` — explicit
- A text message while the user is in `QueryFlow.in_thread` (5-min window).

We don't make all text default-to-query because Mnemo is a capture tool
first; queries must be explicit. The conversational thread starts when the
user types `/q ...` and stays open for 5 minutes (rolling).
"""

from __future__ import annotations

from uuid import UUID

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from mnemo_bot.api_client import ApiClient
from mnemo_bot.keyboards import query_feedback
from mnemo_bot.logging import get_logger
from mnemo_bot.states import QueryFlow

router = Router(name="query")
log = get_logger(__name__)

_THREAD_TTL_SECONDS = 300


@router.message(Command("q"))
async def query_command(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    api: ApiClient,
    tg_user_id: int,
) -> None:
    q = (command.args or "").strip()
    if not q:
        await message.reply("Usage: /q what did I save about ___")
        return
    await _ask(message, state, api, tg_user_id, q)


@router.callback_query(F.data.startswith("qfb:"))
async def query_feedback_cb(
    cq: CallbackQuery, api: ApiClient, tg_user_id: int
) -> None:
    _, qid_str, rating_str = (cq.data or "").split(":")
    try:
        await api.feedback(tg_user_id, UUID(qid_str), int(rating_str))
        await cq.answer("Thanks — recorded.")
    except Exception:
        log.exception("query.feedback.failed", qid=qid_str)
        await cq.answer("Couldn't save feedback.", show_alert=True)


@router.callback_query(F.data.startswith("cite:"))
async def open_citation(
    cq: CallbackQuery, api: ApiClient, tg_user_id: int
) -> None:
    _, nid = (cq.data or "").split(":", 1)
    try:
        note = await api.get_note(tg_user_id, UUID(nid))
    except Exception:
        log.exception("query.cite.fetch_failed", nid=nid)
        await cq.answer("Couldn't fetch the note.", show_alert=True)
        return

    text = "*{title}*\n\n{summary}\n\n_{captured}_".format(
        title=note.get("title") or "(untitled)",
        summary=note.get("summary") or note.get("processed_content") or "(no body)",
        captured=note.get("captured_at", ""),
    )
    if cq.message is not None:
        await cq.message.reply(text[:3_900], parse_mode="Markdown")
    await cq.answer()


async def _ask(
    message: Message,
    state: FSMContext,
    api: ApiClient,
    tg_user_id: int,
    q: str,
) -> None:
    placeholder = await message.reply("🔍 Thinking…")
    try:
        result = await api.query(tg_user_id, q)
    except Exception:
        log.exception("query.api_failed", q=q[:80])
        await placeholder.edit_text("❌ Query failed.")
        return

    answer = result.get("answer", "")
    citations = result.get("citations", [])
    citation_pairs = [(c["short_id"], UUID(c["note_id"])) for c in citations]
    qid = UUID(result["query_id"])

    body = answer.strip() or "I couldn't find anything to back up an answer."
    if citations:
        body += "\n\n— sources below —"
    await placeholder.edit_text(
        body[:4_000], reply_markup=query_feedback(qid, citation_pairs)
    )

    await state.set_state(QueryFlow.in_thread)
    await state.update_data(last_q=q, thread_started_at=tg_user_id)
