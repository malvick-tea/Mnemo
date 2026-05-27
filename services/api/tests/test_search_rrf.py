"""Pure-Python unit tests for the RRF fusion helper.

The full hybrid_search needs Postgres + Qdrant (covered in integration
tests); here we exercise just the fusion math.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from mnemo_api.services.search import _rrf_fuse


def _chunk_ranking(items: list[tuple[UUID, UUID]]) -> list[tuple[UUID, UUID, float]]:
    return [(c, n, 0.0) for c, n in items]


def test_rrf_orders_by_rank_sum() -> None:
    n1, n2, n3 = uuid4(), uuid4(), uuid4()
    c1, c2, c3 = uuid4(), uuid4(), uuid4()
    vec = _chunk_ranking([(c1, n1), (c2, n2), (c3, n3)])
    fts = _chunk_ranking([(c2, n2), (c1, n1), (c3, n3)])
    fused = _rrf_fuse([vec, fts], k=60, labels=("vec", "fts"))
    # c1 and c2 both appear in top-2 across both → tied, then c3.
    assert {fused[0][0], fused[1][0]} == {c1, c2}
    assert fused[2][0] == c3


def test_rrf_empty_inputs() -> None:
    assert _rrf_fuse([[], []], k=60, labels=("vec", "fts")) == []


def test_rrf_handles_disjoint_sets() -> None:
    n1, n2 = uuid4(), uuid4()
    c1, c2 = uuid4(), uuid4()
    vec = _chunk_ranking([(c1, n1)])
    fts = _chunk_ranking([(c2, n2)])
    fused = _rrf_fuse([vec, fts], k=60, labels=("vec", "fts"))
    assert len(fused) == 2
