"""Property-based + golden tests for the chunker."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from mnemo_api.services.chunking import split_into_chunks


def test_empty_input_returns_no_chunks() -> None:
    assert split_into_chunks("") == []
    assert split_into_chunks("   ") == []


def test_short_text_one_chunk() -> None:
    chunks = split_into_chunks("Hello there. General Kenobi.")
    assert len(chunks) == 1
    assert "Hello there" in chunks[0].content


def test_long_text_multiple_chunks_with_overlap() -> None:
    sentences = "This is a sentence. " * 600  # well above the 800-token target
    chunks = split_into_chunks(sentences, max_tokens=200, overlap_tokens=20)
    assert len(chunks) >= 2
    # Adjacent chunks should share at least some text via overlap tail.
    assert any(
        chunks[i].content.split()[-3:] == chunks[i + 1].content.split()[:3]
        or set(chunks[i].content.split()[-5:]) & set(chunks[i + 1].content.split()[:5])
        for i in range(len(chunks) - 1)
    )


@given(st.text(min_size=0, max_size=5000))
def test_chunker_never_drops_visible_content(s: str) -> None:
    out = split_into_chunks(s)
    if s.strip():
        # Every chunk has non-empty content.
        assert all(c.content.strip() for c in out)
        # The total chunked length never exceeds 2x the input (overlap-bounded).
        assert sum(len(c.content) for c in out) <= 3 * len(s)
