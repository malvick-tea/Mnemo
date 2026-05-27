"""RAG eval skeleton — 50 Q&A pairs over a seeded corpus.

For Phase 1 we ship the harness and a minimal 5-pair dataset; the full
50 pairs come in milestone-2 alongside the voice/url capture types.

Run:
    make eval
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.eval


# (corpus_seed_id, question, expected_substring_in_answer)
EVAL_CASES: list[tuple[str, str, str]] = [
    ("pgvector-hnsw", "Which HNSW params worked well for the pgvector dataset?",
     "m=16"),
    ("kitchen-reno", "What sink did I shortlist for the kitchen?",
     "Kraus"),
    ("aiogram3-reasoning", "Why did Mnemo pick aiogram 3?",
     "FSM"),
    ("rrf-adr", "What k value does Mnemo's RRF use?",
     "60"),
    ("rag-citation", "How does Mnemo cite a source in answers?",
     "short id"),
]


@pytest.mark.skip(reason="eval suite requires a seeded corpus; enable in milestone-2")
@pytest.mark.parametrize("seed,question,expected", EVAL_CASES)
def test_rag_eval(seed: str, question: str, expected: str) -> None:  # noqa: ARG001
    # TODO(milestone-2): seed corpus per fixture, run /v1/query, assert
    # expected substring appears in the answer, log recall@5 against a
    # baseline file, fail if drop > 5%.
    raise AssertionError("not implemented")
