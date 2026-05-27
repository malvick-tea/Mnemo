"""Ollama chat & embedding clients (fully local).

Reaches Ollama via HTTP. On Mac/Windows the typical compose-internal URL is
`http://host.docker.internal:11434`; on Linux pass the host IP explicitly.
"""

from __future__ import annotations

from typing import Any, Literal

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from mnemo_api.exceptions import ProviderError
from mnemo_api.llm.base import CompletionResult, Message
from mnemo_api.logging import get_logger

log = get_logger(__name__)


class OllamaClient:
    def __init__(self, base_url: str, *, timeout: float = 120.0) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)

    async def chat(
        self,
        messages: list[Message],
        *,
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.2,
        response_format: Literal["text", "json"] = "text",
        prompt_fingerprint: str | None = None,
    ) -> CompletionResult:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }
        if response_format == "json":
            payload["format"] = "json"

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=0.5, max=10),
                retry=retry_if_exception_type((httpx.HTTPError,)),
                reraise=True,
            ):
                with attempt:
                    resp = await self._client.post("/api/chat", json=payload)
                    resp.raise_for_status()
                    data = resp.json()
        except httpx.HTTPError as exc:
            log.error("ollama.chat.failed", model=model, error=str(exc))
            raise ProviderError(f"Ollama call failed: {exc}") from exc

        return CompletionResult(
            text=data.get("message", {}).get("content", ""),
            model=model,
            prompt_tokens=int(data.get("prompt_eval_count", 0)),
            completion_tokens=int(data.get("eval_count", 0)),
            prompt_fingerprint=prompt_fingerprint,
        )

    async def aclose(self) -> None:
        await self._client.aclose()


class OllamaEmbedder:
    def __init__(self, base_url: str, model: str, dim: int, *, timeout: float = 60.0) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)
        self._model = model
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            resp = await self._client.post(
                "/api/embed",
                json={"model": self._model, "input": texts},
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            log.error("ollama.embed.failed", model=self._model, error=str(exc))
            raise ProviderError(f"Ollama embed failed: {exc}") from exc

        vectors = data.get("embeddings") or []
        if not vectors or len(vectors[0]) != self._dim:
            raise ProviderError(
                f"Embedding dim mismatch: configured {self._dim}, "
                f"got {len(vectors[0]) if vectors else 0}"
            )
        return list(vectors)

    async def embed_one(self, text: str) -> list[float]:
        out = await self.embed([text])
        return out[0]

    async def aclose(self) -> None:
        await self._client.aclose()
