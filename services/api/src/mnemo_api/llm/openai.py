"""OpenAI embedder (for `MNEMO_EMBED_PROVIDER=openai`).

Chat completions for OpenAI proper go through the OpenRouter client by
convention — there's no separate OpenAIChat class. We only ship an embedder
here because OpenRouter's embedding coverage is thin.
"""

from __future__ import annotations

import httpx

from mnemo_api.exceptions import ProviderError
from mnemo_api.logging import get_logger

log = get_logger(__name__)


class OpenAIEmbedder:
    def __init__(self, api_key: str, model: str, dim: int, *, timeout: float = 60.0) -> None:
        self._client = httpx.AsyncClient(
            base_url="https://api.openai.com/v1",
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        self._model = model
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            resp = await self._client.post(
                "/embeddings",
                json={"model": self._model, "input": texts},
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            log.error("openai.embed.failed", model=self._model, error=str(exc))
            raise ProviderError(f"OpenAI embed failed: {exc}") from exc

        return [item["embedding"] for item in data["data"]]

    async def embed_one(self, text: str) -> list[float]:
        out = await self.embed([text])
        return out[0]

    async def aclose(self) -> None:
        await self._client.aclose()
