"""Summarize a piece of content. Called from workers."""

from __future__ import annotations

from mnemo_api.config import get_settings
from mnemo_api.llm import LLMClient, Message, render_prompt


async def summarize(
    llm: LLMClient,
    *,
    content: str,
    source_type: str,
    title_hint: str | None = None,
    max_words: int = 120,
) -> str:
    settings = get_settings()
    prompt, fp = render_prompt(
        "summarize_v1",
        content=content,
        source_type=source_type,
        title_hint=title_hint,
        max_words=max_words,
    )
    completion = await llm.chat(
        [Message(role="user", content=prompt)],
        model=settings.model_summarize,
        max_tokens=400,
        temperature=0.2,
        prompt_fingerprint=fp,
    )
    return completion.text.strip()
