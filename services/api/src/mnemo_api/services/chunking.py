"""Token-aware chunking with sentence-boundary preference.

We avoid pulling a tokenizer into the API image (heavy dep, model-coupled);
instead we estimate tokens at ~4 chars/token, which is good enough to keep
chunks under the embedder's input limit. Workers may pass a real token
counter if available — the splitter accepts either.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

DEFAULT_MAX_TOKENS = 800
DEFAULT_OVERLAP_TOKENS = 80

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-ZА-Я0-9\"'(\[])")


def _est_tokens(s: str) -> int:
    return max(1, len(s) // 4)


@dataclass(slots=True)
class Chunk:
    index: int
    content: str
    token_count: int


def split_into_chunks(
    text: str,
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
    count_tokens: Callable[[str], int] = _est_tokens,
) -> list[Chunk]:
    """Greedy sentence-pack into max_tokens with `overlap_tokens` of carryover.

    For very long unsentenced text (e.g. transcript without punctuation) we
    fall back to fixed-size character slices.
    """
    text = (text or "").strip()
    if not text:
        return []

    sentences = _SENT_SPLIT.split(text) if _SENT_SPLIT.search(text) else None
    if not sentences or all(count_tokens(s) > max_tokens for s in sentences):
        return _slice_by_chars(text, max_tokens, count_tokens)

    chunks: list[Chunk] = []
    buf: list[str] = []
    buf_toks = 0
    idx = 0
    for sent in sentences:
        st = count_tokens(sent)
        if buf and buf_toks + st > max_tokens:
            chunks.append(Chunk(idx, " ".join(buf).strip(), buf_toks))
            idx += 1
            # Build overlap tail
            tail: list[str] = []
            tail_toks = 0
            for s in reversed(buf):
                ts = count_tokens(s)
                if tail_toks + ts > overlap_tokens:
                    break
                tail.insert(0, s)
                tail_toks += ts
            buf = tail
            buf_toks = tail_toks
        buf.append(sent)
        buf_toks += st

    if buf:
        chunks.append(Chunk(idx, " ".join(buf).strip(), buf_toks))
    return chunks


def _slice_by_chars(
    text: str, max_tokens: int, count_tokens: Callable[[str], int]
) -> list[Chunk]:
    target_chars = max_tokens * 4
    out: list[Chunk] = []
    for i in range(0, len(text), target_chars):
        slice_ = text[i : i + target_chars]
        out.append(Chunk(len(out), slice_, count_tokens(slice_)))
    return out
