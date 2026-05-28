"""Boot-time wiring: pick a provider from settings and instantiate clients."""

from __future__ import annotations

from mnemo_api.config import Settings
from mnemo_api.exceptions import MnemoError
from mnemo_api.llm.base import Embedder, LLMClient
from mnemo_api.llm.ollama import OllamaClient, OllamaEmbedder
from mnemo_api.llm.openai import OpenAIEmbedder
from mnemo_api.llm.openrouter import OpenRouterClient


def make_llm(settings: Settings) -> LLMClient:
    if settings.llm_provider == "openrouter":
        if not settings.openrouter_api_key:
            raise MnemoError(
                "MNEMO_LLM_PROVIDER=openrouter requires OPENROUTER_API_KEY"
            )
        return OpenRouterClient(
            base_url=settings.openrouter_base_url,
            api_key=settings.openrouter_api_key.get_secret_value(),
        )
    if settings.llm_provider == "ollama":
        return OllamaClient(base_url=settings.ollama_base_url)
    raise MnemoError(f"Unknown LLM provider: {settings.llm_provider}")


def make_vision_llm(settings: Settings) -> OpenRouterClient:
    """Vision capture requires OpenRouter regardless of MNEMO_LLM_PROVIDER.

    Ollama vision (llava etc.) is planned for milestone-3 — until then we
    require an OpenRouter key to enable photo capture.
    """
    if not settings.openrouter_api_key:
        raise MnemoError(
            "Vision (photo capture) requires OPENROUTER_API_KEY. "
            "Ollama-native vision is on the milestone-3 roadmap."
        )
    return OpenRouterClient(
        base_url=settings.openrouter_base_url,
        api_key=settings.openrouter_api_key.get_secret_value(),
    )


def make_embedder(settings: Settings) -> Embedder:
    if settings.embed_provider == "ollama":
        return OllamaEmbedder(
            base_url=settings.ollama_base_url,
            model=settings.embed_model,
            dim=settings.embed_dim,
        )
    if settings.embed_provider == "openai":
        if not settings.openai_api_key:
            raise MnemoError(
                "MNEMO_EMBED_PROVIDER=openai requires OPENAI_API_KEY"
            )
        return OpenAIEmbedder(
            api_key=settings.openai_api_key.get_secret_value(),
            model=settings.embed_model,
            dim=settings.embed_dim,
        )
    raise MnemoError(f"Unknown embed provider: {settings.embed_provider}")
