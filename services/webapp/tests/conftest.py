from __future__ import annotations

import base64
import os
import secrets

os.environ.setdefault("MNEMO_SERVICE_JWT_SECRET", secrets.token_urlsafe(48))
os.environ.setdefault("MNEMO_WEBHOOK_HMAC_SECRET", secrets.token_urlsafe(48))
os.environ.setdefault(
    "MNEMO_ENCRYPTION_KEY",
    base64.b64encode(secrets.token_bytes(32)).decode("ascii"),
)
os.environ.setdefault("POSTGRES_USER", "mnemo")
os.environ.setdefault("POSTGRES_PASSWORD", "mnemo")
os.environ.setdefault("POSTGRES_DB", "mnemo_test")
os.environ.setdefault("MINIO_ACCESS_KEY", "mnemo")
os.environ.setdefault("MINIO_SECRET_KEY", "mnemo_secret")
os.environ.setdefault("MNEMO_LLM_PROVIDER", "ollama")
os.environ.setdefault("MNEMO_METRICS_ENABLED", "false")
