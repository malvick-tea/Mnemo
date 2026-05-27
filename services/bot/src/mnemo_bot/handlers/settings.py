"""/settings menu — surface preferences and integration toggles."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from mnemo_bot.api_client import ApiClient
from mnemo_bot.keyboards import settings_menu
from mnemo_bot.logging import get_logger

router = Router(name="settings")
log = get_logger(__name__)


@router.message(Command("settings"))
async def settings_command(message: Message, api: ApiClient, tg_user_id: int) -> None:
    try:
        cfg = await api.get_settings(tg_user_id)
    except Exception:
        log.exception("settings.fetch_failed")
        await message.reply("❌ Couldn't load settings.")
        return
    s = cfg.get("settings", {}) or {}
    text = (
        "*Settings*\n\n"
        f"🤖 Model: `{s.get('model', 'default')}`\n"
        f"🌐 Language: `{s.get('language', 'auto')}`\n"
        f"🔔 Daily digest: `{s.get('daily_digest_time', 'off')}`\n"
        f"🔒 Privacy mode: `{s.get('privacy_mode', 'strict')}`\n"
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=settings_menu())
