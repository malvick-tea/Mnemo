"""LLM adapter layer.

A single `LLMClient` protocol with provider-specific implementations.
Adding a new provider should take ~80 LOC.
"""

from mnemo_api.llm.base import CompletionResult, LLMClient, Message
from mnemo_api.llm.factory import make_embedder, make_llm
from mnemo_api.llm.prompts import render_prompt

__all__ = [
    "CompletionResult",
    "LLMClient",
    "Message",
    "make_embedder",
    "make_llm",
    "render_prompt",
]
