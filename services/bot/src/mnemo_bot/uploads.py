"""Upload size helpers.

Telegram tells us a file's size up front (``file_size``), so we can reject an
oversized attachment before downloading it into memory and POSTing it to the
API — instead of buffering the whole blob just to have the API reject it.
"""

from __future__ import annotations

from mnemo_bot.config import get_settings


def exceeds_limit(file_size: int | None) -> bool:
    """True if Telegram reports a size above the configured cap.

    Unknown size (``None``) is allowed through; the API still enforces the cap.
    """
    if file_size is None:
        return False
    return file_size > get_settings().max_upload_mb * 1024 * 1024
