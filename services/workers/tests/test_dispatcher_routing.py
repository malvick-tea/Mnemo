"""The dispatcher must route Redis markers to the right Dramatiq actor."""

from __future__ import annotations

from mnemo_workers.dispatcher import _ACTORS


def test_known_tasks_registered() -> None:
    expected = {
        "process_text_note",
        "process_voice_note",
        "process_photo_note",
        "process_document_note",
        "embed_note",
        "summarize_note",
        "tag_note",
        "trigger_n8n_workflow",
    }
    assert expected.issubset(_ACTORS.keys())


def test_actor_send_callable() -> None:
    # Each registered entry must expose a Dramatiq-style `.send` attribute.
    for name, actor in _ACTORS.items():
        assert hasattr(actor, "send"), f"{name} is missing .send()"
