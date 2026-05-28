"""Pydantic API schemas (DTOs)."""

from mnemo_api.schemas.capture import (
    CaptureForwardIn,
    CaptureResponse,
    CaptureTextIn,
    CaptureURLIn,
    ForwardMetadata,
)
from mnemo_api.schemas.note import (
    AnkiCardOut,
    AnkiCardsOut,
    NoteOut,
    NotePatch,
    TagOut,
)
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
    "AnkiCardOut",
    "AnkiCardsOut",
    "CaptureForwardIn",
    "CaptureResponse",
    "CaptureTextIn",
    "CaptureURLIn",
    "Citation",
    "ForwardMetadata",
    "N8NNoteFailedIn",
    "N8NNoteReadyIn",
    "NoteOut",
    "NotePatch",
    "QueryFeedbackIn",
    "QueryIn",
    "QueryOut",
    "TagOut",
]
