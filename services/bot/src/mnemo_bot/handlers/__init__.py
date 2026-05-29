"""All handlers — registered in `mnemo_bot.main`."""

from mnemo_bot.handlers import (
    anki,
    capture_document,
    capture_forward,
    capture_photo,
    capture_text,
    capture_url,
    capture_voice,
    digest,
    list_views,
    note_actions,
    query,
    settings,
    start,
)

__all__ = [
    "anki",
    "capture_document",
    "capture_forward",
    "capture_photo",
    "capture_text",
    "capture_url",
    "capture_voice",
    "digest",
    "list_views",
    "note_actions",
    "query",
    "settings",
    "start",
]
