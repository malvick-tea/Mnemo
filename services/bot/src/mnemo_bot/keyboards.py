"""Inline keyboards used across handlers."""

from __future__ import annotations

from uuid import UUID

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def note_actions(note_id: UUID) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🏷 Tags", callback_data=f"note:tags:{note_id}"),
                InlineKeyboardButton(text="📝 Edit", callback_data=f"note:edit:{note_id}"),
                InlineKeyboardButton(text="🗑 Delete", callback_data=f"note:delete:{note_id}"),
            ],
            [
                InlineKeyboardButton(text="🎴 Anki", callback_data=f"note:anki:{note_id}"),
            ],
        ]
    )


def query_feedback(query_id: UUID, citations: list[tuple[str, UUID]]) -> InlineKeyboardMarkup:
    citation_row = [
        InlineKeyboardButton(text=f"[{short}]", callback_data=f"cite:{nid}")
        for short, nid in citations[:5]
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            citation_row or [InlineKeyboardButton(text="—", callback_data="noop")],
            [
                InlineKeyboardButton(text="👍", callback_data=f"qfb:{query_id}:1"),
                InlineKeyboardButton(text="👎", callback_data=f"qfb:{query_id}:-1"),
            ],
        ]
    )


def settings_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🤖 Model", callback_data="set:model")],
            [InlineKeyboardButton(text="🌐 Language", callback_data="set:lang")],
            [InlineKeyboardButton(text="🔔 Daily digest", callback_data="set:digest")],
            [InlineKeyboardButton(text="🔌 Integrations", callback_data="set:integrations")],
            [InlineKeyboardButton(text="🔒 Privacy", callback_data="set:privacy")],
        ]
    )
