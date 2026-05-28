"""Centralised Prometheus metrics.

We declare every counter / histogram here so it's easy to enumerate
what's exposed at `/metrics` and keep label cardinality bounded. Other
modules just `from mnemo_api.metrics import capture_total` and increment.

Cardinality rule: labels are bounded enums (source_type, status,
provider). Never user-controlled strings; route templates are fine
since FastAPI normalises them.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ── Capture ──────────────────────────────────────────────────────────────────

capture_total = Counter(
    "mnemo_capture_total",
    "Notes captured, grouped by source_type and outcome.",
    labelnames=("source_type", "outcome"),  # outcome = ok|rejected|error
)

capture_bytes = Counter(
    "mnemo_capture_bytes_total",
    "Total bytes ingested via capture endpoints (multipart uploads).",
    labelnames=("source_type",),
)

# ── Query / RAG ──────────────────────────────────────────────────────────────

query_total = Counter(
    "mnemo_query_total",
    "RAG queries, grouped by outcome.",
    labelnames=("outcome",),  # ok|empty|error
)

query_latency_seconds = Histogram(
    "mnemo_query_latency_seconds",
    "End-to-end /v1/query latency (search + LLM + citations).",
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 60.0),
)

search_hits = Histogram(
    "mnemo_search_hits",
    "Number of candidates returned by hybrid search.",
    labelnames=("retriever",),  # vec|fts|fused
    buckets=(0, 1, 2, 4, 8, 16, 32, 64),
)

# ── LLM ──────────────────────────────────────────────────────────────────────

llm_tokens_total = Counter(
    "mnemo_llm_tokens_total",
    "LLM tokens consumed, split by direction and provider.",
    labelnames=("direction", "provider"),  # direction = prompt|completion
)

llm_call_seconds = Histogram(
    "mnemo_llm_call_seconds",
    "LLM call latency.",
    labelnames=("provider",),
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 60.0),
)

llm_errors_total = Counter(
    "mnemo_llm_errors_total",
    "LLM provider errors (retries exhausted).",
    labelnames=("provider",),
)

# ── Workers / queues ─────────────────────────────────────────────────────────

worker_task_total = Counter(
    "mnemo_worker_task_total",
    "Worker actor invocations, grouped by actor and outcome.",
    labelnames=("actor", "outcome"),  # outcome = ok|error|skipped
)

worker_task_seconds = Histogram(
    "mnemo_worker_task_seconds",
    "Worker actor wall-clock duration.",
    labelnames=("actor",),
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 300.0),
)

queue_depth = Gauge(
    "mnemo_queue_depth",
    "Length of the API → workers handoff queue (Redis LLEN mnemo:tasks).",
)

# ── Webhooks ─────────────────────────────────────────────────────────────────

webhook_total = Counter(
    "mnemo_webhook_total",
    "Inbound n8n webhooks, grouped by event and outcome.",
    labelnames=("event", "outcome"),  # outcome = accepted|duplicate|rejected|error
)
