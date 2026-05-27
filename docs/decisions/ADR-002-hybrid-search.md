# ADR-002: Hybrid search with Reciprocal Rank Fusion

- **Status:** accepted
- **Date:** 2026-02-03

## Context

Mnemo needs to retrieve relevant chunks for `/v1/query`. Pure semantic
(vector) search misses exact-name matches ("the *pgvector* paper") and rare
tokens; pure keyword search (BM25 / `tsvector`) misses paraphrased queries
("the article about ANN indexes in Postgres"). We must combine them.

Three obvious blends:
1. Weighted sum of normalized scores `α·vec + (1-α)·fts`.
2. Reciprocal Rank Fusion (RRF): `Σ 1/(k + rank_i)`.
3. Two-stage: vector recall → cross-encoder rerank only.

## Decision

Default to **RRF with k=60** over a 20-candidate vector list and 20-candidate
FTS list, returning the top-`k` (default 8). A cross-encoder reranker
(`bge-reranker-v2-m3`) is wired in but **off by default** behind
`MNEMO_USE_RERANKER`.

## Consequences

**Good:**
- RRF needs no per-corpus tuning: no normalization across heterogeneous
  scoring scales (Qdrant cosine vs `ts_rank_cd`).
- Robust to one side returning low-quality scores — the *rank* matters, not
  the score.
- Implementation is ~20 lines of pure Python.

**Trade-off:**
- We forfeit some headroom that a calibrated weighted-sum or a learned
  reranker could give us. Mitigated by leaving the reranker as a feature
  flag; users with a GPU can flip it on.

## Alternatives considered

- **Weighted sum:** needs per-corpus calibration. Mnemo corpora vary by user
  size and topic; no good universal α.
- **Cross-encoder only:** slow without a GPU, and we still need a recall
  step in front of it — which is what RRF already gives us.
- **Hybrid vector** (e.g. SPLADE): adds an index type to Qdrant we don't
  currently use; can revisit in Phase 3.
