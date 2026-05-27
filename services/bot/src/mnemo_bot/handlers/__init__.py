"""All handlers — registered in `mnemo_bot.main`."""

from mnemo_bot.handlers import (
    capture_document,
    capture_forward,
    capture_photo,
    capture_text,
    capture_url,
    capture_voice,
    digest,
    query,
    settings,
    start,
)

__all__ = [
    "capture_document",
    "capture_forward",
    "capture_photo",
    "capture_text",
    "capture_url",
    "capture_voice",
    "digest",
    "query",
    "settings",
    "start",
]
