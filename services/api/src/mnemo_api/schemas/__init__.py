"""Pydantic API schemas (DTOs)."""

from mnemo_api.schemas.capture import (
    CaptureTextIn,
    CaptureURLIn,
    CaptureResponse,
)
from mnemo_api.schemas.note import NoteOut, NotePatch, TagOut
from mnemo_api.schemas.query import (
    Citation,
    QueryFeedbackIn,
    QueryIn,
    QueryOut,
)
from mnemo_api.schemas.webhooks import (
    N8NNoteFailedIn,
    N8NNoteReadyIn,
)

__all__ = [
    "CaptureResponse",
    "CaptureTextIn",
    "CaptureURLIn",
    "Citation",
    "N8NNoteFailedIn",
    "N8NNoteReadyIn",
    "NoteOut",
    "NotePatch",
    "QueryFeedbackIn",
    "QueryIn",
    "QueryOut",
    "TagOut",
]
