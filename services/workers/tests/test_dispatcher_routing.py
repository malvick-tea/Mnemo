"""The dispatcher must route Redis markers to the right Dramatiq actor."""

from __future__ import annotations

from mnemo_workers.dispatcher import _ACTORS


def test_known_tasks_registered() -> None:
    assert "process_text_note" in _ACTORS
    assert "embed_note" in _ACTORS
    assert "summarize_note" in _ACTORS
    assert "tag_note" in _ACTORS
    assert "trigger_n8n_workflow" in _ACTORS
