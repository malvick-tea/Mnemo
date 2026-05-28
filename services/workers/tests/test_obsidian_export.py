"""Smoke tests for the Obsidian export renderer.

The full periodic flow needs Postgres + Integration rows; here we test the
two pure helpers (`_safe_filename`, `_render_markdown`) that decide the
on-disk format.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

from mnemo_workers.tasks.obsidian_export import (
    _render_markdown,
    _safe_filename,
)


def _note(**overrides: object) -> object:
    base = SimpleNamespace(
        id=UUID("12345678-1234-5678-1234-567812345678"),
        title="My title",
        summary="A short summary.",
        processed_content="The body of the note.",
        raw_content=None,
        source_type="text",
        source_url=None,
        captured_at=datetime(2026, 5, 28, 9, 0, tzinfo=UTC),
        created_at=datetime(2026, 5, 28, 9, 0, tzinfo=UTC),
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


def test_filename_is_safe() -> None:
    n = _note(title="Hello: world?!")
    out = _safe_filename(n)
    assert out.endswith(".md")
    assert ":" not in out and "?" not in out
    assert out.startswith("2026-05-28-")


def test_filename_handles_empty_title() -> None:
    n = _note(title=None)
    assert _safe_filename(n).startswith("2026-05-28-untitled-")


def test_render_includes_frontmatter_and_body() -> None:
    n = _note(source_url="https://example.com")
    md = _render_markdown(n, tags=["python", "ml"])
    assert md.startswith("---\n")
    assert "title:" in md
    assert "source_type: text" in md
    assert "source_url: https://example.com" in md
    assert 'tags: ["python", "ml"]' in md
    assert "> A short summary." in md
    assert "The body of the note." in md


def test_render_falls_back_to_raw_content() -> None:
    n = _note(processed_content=None, raw_content="raw only")
    md = _render_markdown(n, tags=[])
    assert "raw only" in md
