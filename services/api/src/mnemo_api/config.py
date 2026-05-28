"""Application configuration loaded from environment.

We use Pydantic Settings so the app fails fast and loud on missing or
malformed config rather than blowing up the first time the value is read.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_TOKENS = frozenset({"changeme", "changeme_32b_hex_or_longer", ""})


class Settings(BaseSettings):
    """Strict typed config. Bombs on placeholder secrets so prod is safe."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=("settings_",),
    )

    # ── Deployment ──────────────────────────────────────────────────────────
    env: Literal["development", "production"] = Field(default="production", alias="MNEMO_ENV")
    log_level: str = Field(default="INFO", alias="MNEMO_LOG_LEVEL")
    log_pii: bool = Field(default=False, alias="MNEMO_LOG_PII")

    # ── Auth ────────────────────────────────────────────────────────────────
    service_jwt_secret: SecretStr = Field(alias="MNEMO_SERVICE_JWT_SECRET")
    webhook_hmac_secret: SecretStr = Field(alias="MNEMO_WEBHOOK_HMAC_SECRET")
    encryption_key: SecretStr = Field(alias="MNEMO_ENCRYPTION_KEY")
    allowed_tg_ids: str = Field(default="", alias="MNEMO_ALLOWED_TG_IDS")

    # ── Postgres ────────────────────────────────────────────────────────────
    postgres_user: str = Field(alias="POSTGRES_USER")
    postgres_password: SecretStr = Field(alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(alias="POSTGRES_DB")
    postgres_host: str = Field(default="postgres", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")

    # ── Qdrant ──────────────────────────────────────────────────────────────
    qdrant_url: str = Field(default="http://qdrant:6333", alias="QDRANT_URL")
    qdrant_api_key: SecretStr | None = Field(default=None, alias="QDRANT_API_KEY")
    qdrant_collection: str = "mnemo_chunks"

    # ── Redis ───────────────────────────────────────────────────────────────
    redis_url: str = Field(default="redis://redis:6379/0", alias="REDIS_URL")

    # ── MinIO ───────────────────────────────────────────────────────────────
    minio_endpoint: str = Field(default="minio:9000", alias="MINIO_ENDPOINT")
    minio_access_key: str = Field(alias="MINIO_ACCESS_KEY")
    minio_secret_key: SecretStr = Field(alias="MINIO_SECRET_KEY")
    minio_bucket: str = Field(default="mnemo-blobs", alias="MINIO_BUCKET")
    minio_use_tls: bool = Field(default=False, alias="MINIO_USE_TLS")

    # ── n8n ─────────────────────────────────────────────────────────────────
    n8n_base_url: str = Field(default="http://n8n:5678", alias="N8N_BASE_URL")

    # ── AI providers ────────────────────────────────────────────────────────
    llm_provider: Literal["openrouter", "ollama"] = Field(
        default="openrouter", alias="MNEMO_LLM_PROVIDER"
    )
    openrouter_api_key: SecretStr | None = Field(default=None, alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1", alias="OPENROUTER_BASE_URL"
    )
    openai_api_key: SecretStr | None = Field(default=None, alias="OPENAI_API_KEY")
    ollama_base_url: str = Field(
        default="http://host.docker.internal:11434", alias="OLLAMA_BASE_URL"
    )

    # Per-job model routing. Defaults reflect the May 2026 frontier:
    # - summarize/tag: cheap+fast → Gemini 3.5 Flash (Google I/O 2026-05-19)
    # - rag: quality-critical → Claude Opus 4.7 (Anthropic 2026-04-16)
    # - vision: 3.75-megapixel native vision in Opus 4.7; reuse it
    # Swap to anything OpenRouter exposes by changing the env var.
    model_summarize: str = Field(default="google/gemini-3.5-flash", alias="MNEMO_MODEL_SUMMARIZE")
    model_tag: str = Field(default="google/gemini-3.5-flash", alias="MNEMO_MODEL_TAG")
    model_rag: str = Field(default="anthropic/claude-opus-4.7", alias="MNEMO_MODEL_RAG")
    model_vision: str = Field(default="anthropic/claude-opus-4.7", alias="MNEMO_MODEL_VISION")

    embed_provider: Literal["ollama", "openai"] = Field(
        default="ollama", alias="MNEMO_EMBED_PROVIDER"
    )
    embed_model: str = Field(default="bge-m3", alias="MNEMO_EMBED_MODEL")
    embed_dim: int = Field(default=1024, alias="MNEMO_EMBED_DIM")

    use_reranker: bool = Field(default=False, alias="MNEMO_USE_RERANKER")
    rerank_model: str = Field(default="BAAI/bge-reranker-v2-m3", alias="MNEMO_RERANK_MODEL")

    user_daily_token_cap: int = Field(default=200_000, alias="MNEMO_USER_DAILY_TOKEN_CAP")

    # ── Limits ──────────────────────────────────────────────────────────────
    max_upload_mb: int = Field(default=50, alias="MNEMO_MAX_UPLOAD_MB")
    throttle_per_min: int = Field(default=10, alias="MNEMO_THROTTLE_PER_MIN")

    # ── Observability ───────────────────────────────────────────────────────
    metrics_enabled: bool = Field(default=True, alias="MNEMO_METRICS_ENABLED")
    otel_enabled: bool = Field(default=False, alias="MNEMO_OTEL_ENABLED")

    # ── Computed ────────────────────────────────────────────────────────────
    @property
    def postgres_dsn(self) -> str:
        pw = self.postgres_password.get_secret_value()
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{pw}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def allowed_tg_ids_set(self) -> frozenset[int]:
        if not self.allowed_tg_ids:
            return frozenset()
        return frozenset(int(x.strip()) for x in self.allowed_tg_ids.split(",") if x.strip())

    # ── Validators ──────────────────────────────────────────────────────────
    @field_validator(
        "service_jwt_secret",
        "webhook_hmac_secret",
        "encryption_key",
        "postgres_password",
        "minio_secret_key",
        mode="after",
    )
    @classmethod
    def _reject_placeholders(cls, v: SecretStr) -> SecretStr:
        val = v.get_secret_value().lower()
        if val in _PLACEHOLDER_TOKENS:
            raise ValueError(
                "Refusing to start with a placeholder/default secret. "
                "Run `./scripts/bootstrap.sh` or edit .env."
            )
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
