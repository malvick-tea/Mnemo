"""OpenRouter chat & embedding clients.

OpenRouter exposes an OpenAI-compatible REST API across many providers, so
we keep the wire format OpenAI-shaped. Embeddings via OpenRouter are not
universally supported — for embeddings prefer Ollama (bge-m3) or OpenAI.
"""

from __future__ import annotations

import base64
import time
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
from mnemo_api.metrics import llm_call_seconds, llm_errors_total, llm_tokens_total

log = get_logger(__name__)

_PROVIDER = "openrouter"


class OpenRouterClient:
    """Thin OpenAI-compatible client. 3-retry with exponential backoff."""

    def __init__(self, base_url: str, api_key: str, *, timeout: float = 60.0) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "X-Title": "Mnemo",
            },
        )

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
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        return await self._call(payload, model, prompt_fingerprint)

    async def chat_vision(
        self,
        *,
        prompt: str,
        image_bytes: bytes,
        mime: str,
        model: str,
        max_tokens: int = 800,
        temperature: float = 0.2,
        prompt_fingerprint: str | None = None,
    ) -> CompletionResult:
        """Multi-modal call with one image. Returns the text description.

        We inline the image as a data URL — keeps the call stateless and
        avoids exposing MinIO. ~3-4x the bytes vs raw, fine for ≤10 MB.
        """
        b64 = base64.b64encode(image_bytes).decode("ascii")
        data_url = f"data:{mime};base64,{b64}"
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        return await self._call(payload, model, prompt_fingerprint)

    async def _call(
        self,
        payload: dict[str, Any],
        model: str,
        prompt_fingerprint: str | None,
    ) -> CompletionResult:
        retrying = AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=0.5, max=10),
            retry=retry_if_exception_type((httpx.HTTPError,)),
            reraise=True,
        )
        t0 = time.perf_counter()
        try:
            async for attempt in retrying:
                with attempt:
                    resp = await self._client.post("/chat/completions", json=payload)
                    if resp.status_code >= 500:
                        raise httpx.HTTPStatusError(
                            "upstream 5xx", request=resp.request, response=resp
                        )
                    resp.raise_for_status()
                    data = resp.json()
        except httpx.HTTPError as exc:
            llm_errors_total.labels(provider=_PROVIDER).inc()
            llm_call_seconds.labels(provider=_PROVIDER).observe(time.perf_counter() - t0)
            log.error("openrouter.chat.failed", model=model, error=str(exc))
            raise ProviderError(f"OpenRouter call failed: {exc}") from exc

        llm_call_seconds.labels(provider=_PROVIDER).observe(time.perf_counter() - t0)
        choice = data["choices"][0]
        usage = data.get("usage", {})
        prompt_tokens = int(usage.get("prompt_tokens", 0))
        completion_tokens = int(usage.get("completion_tokens", 0))
        if prompt_tokens:
            llm_tokens_total.labels(direction="prompt", provider=_PROVIDER).inc(prompt_tokens)
        if completion_tokens:
            llm_tokens_total.labels(direction="completion", provider=_PROVIDER).inc(completion_tokens)
        return CompletionResult(
            text=choice["message"]["content"] or "",
            model=data.get("model", model),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            prompt_fingerprint=prompt_fingerprint,
        )

    async def aclose(self) -> None:
        await self._client.aclose()
