"""LLMClient protocol + shared types.

A provider implementation is a 60-100 LOC class that:
- accepts a model name, max_tokens, temperature, and either text/json output;
- returns a `CompletionResult` with the text, token usage, and prompt fingerprint;
- raises `ProviderError` on any non-recoverable upstream failure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

Role = Literal["system", "user", "assistant"]


@dataclass(slots=True, frozen=True)
class Message:
    role: Role
    content: str


@dataclass(slots=True, frozen=True)
class CompletionResult:
    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    # Filename + version of the prompt template that produced this call.
    # Stamped onto query logs so we can correlate behaviour changes with
    # prompt edits.
    prompt_fingerprint: str | None = None

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@runtime_checkable
class LLMClient(Protocol):
    async def chat(
        self,
        messages: list[Message],
        *,
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.2,
        response_format: Literal["text", "json"] = "text",
        prompt_fingerprint: str | None = None,
    ) -> CompletionResult: ...


@runtime_checkable
class Embedder(Protocol):
    @property
    def dim(self) -> int: ...

    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_one(self, text: str) -> list[float]: ...
