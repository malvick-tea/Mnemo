"""Bot config (lighter than the API's — only what the bot needs)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER = frozenset({"changeme", ""})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: Literal["development", "production"] = Field(default="production", alias="MNEMO_ENV")
    log_level: str = Field(default="INFO", alias="MNEMO_LOG_LEVEL")

    tg_token: SecretStr = Field(alias="TELEGRAM_BOT_TOKEN")
    tg_mode: Literal["webhook", "polling"] = Field(default="polling", alias="TELEGRAM_MODE")
    tg_webhook_path: str = Field(default="/telegram", alias="TELEGRAM_WEBHOOK_PATH")
    tg_webhook_port: int = Field(default=8080, alias="TELEGRAM_WEBHOOK_PORT")

    allowed_tg_ids: str = Field(default="", alias="MNEMO_ALLOWED_TG_IDS")
    throttle_per_min: int = Field(default=10, alias="MNEMO_THROTTLE_PER_MIN")

    api_base_url: str = Field(default="http://api:8000", alias="MNEMO_API_BASE_URL")
    service_jwt_secret: SecretStr = Field(alias="MNEMO_SERVICE_JWT_SECRET")

    redis_url: str = Field(default="redis://redis:6379/0", alias="REDIS_URL")

    domain: str = Field(default="localhost", alias="MNEMO_DOMAIN")

    @field_validator("tg_token", "service_jwt_secret", mode="after")
    @classmethod
    def _reject_placeholders(cls, v: SecretStr) -> SecretStr:
        if v.get_secret_value().lower() in _PLACEHOLDER:
            raise ValueError("Refusing to start with placeholder secret. Run bootstrap.sh.")
        return v

    @property
    def allowed_tg_ids_set(self) -> frozenset[int]:
        if not self.allowed_tg_ids:
            return frozenset()
        return frozenset(int(x.strip()) for x in self.allowed_tg_ids.split(",") if x.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
