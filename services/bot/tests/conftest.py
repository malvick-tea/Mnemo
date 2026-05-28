"""Bot tests set their own env so config validators pass."""

from __future__ import annotations

import os
import secrets

os.environ.setdefault("TELEGRAM_BOT_TOKEN", f"1:{secrets.token_urlsafe(24)}")
os.environ.setdefault("MNEMO_SERVICE_JWT_SECRET", secrets.token_urlsafe(48))
os.environ.setdefault("MNEMO_ALLOWED_TG_IDS", "100,200")
