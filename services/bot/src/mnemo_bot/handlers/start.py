"""/start, /help, /cancel."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

router = Router(name="start")

_WELCOME = (
    "👋 Welcome to *Mnemo* — your self-hosted second brain.\n\n"
    "Send me anything and I'll capture it:\n"
    "• plain text → saved\n"
    "• 🎙 voice → transcribed + saved\n"
    "• 🔗 URL → fetched + summarized\n"
    "• 📄 document → parsed + saved\n\n"
    "Ask me anything with `/q your question`.\n"
    "See `/help` for all commands.\n"
)

_HELP = (
    "*Commands*\n"
    "`/q <question>` — ask a grounded question\n"
    "`/save <text>` — explicitly save text\n"
    "`/recent` — last 10 captures\n"
    "`/tags` — your tag cloud\n"
    "`/digest` — today's digest\n"
    "`/settings` — preferences\n"
    "`/cancel` — drop current conversation thread\n"
    "`/export` — export everything as a zip\n\n"
    "*Tips*\n"
    "• Forward any message to me; I'll keep the source.\n"
    "• Send a photo with a caption — I'll OCR and tag it.\n"
    "• I keep your data local. Nothing leaves your server unless "
    "you turn on a cloud LLM provider.\n"
)


@router.message(Command("start"))
async def start(message: Message) -> None:
    await message.answer(_WELCOME, parse_mode="Markdown")


@router.message(Command("help"))
async def help_(message: Message) -> None:
    await message.answer(_HELP, parse_mode="Markdown")


@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("OK, fresh thread.")
