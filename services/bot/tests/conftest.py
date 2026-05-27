"""Bot tests set their own env so config validators pass."""

from __future__ import annotations

import os

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "1:abcDEF")
os.environ.setdefault("MNEMO_SERVICE_JWT_SECRET", "x" * 64)
os.environ.setdefault("MNEMO_ALLOWED_TG_IDS", "100,200")
