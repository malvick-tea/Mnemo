"""Smoke tests for the central metrics module.

The registry is global (Prometheus client). We just verify the named
metrics exist with the expected label sets so a typo elsewhere in the
codebase blows up at import time rather than silently dropping samples.
"""

from __future__ import annotations

from mnemo_api import metrics


def _sample_names(collector: object) -> set[str]:
    return {
        sample.name
        for metric in collector.collect()  # type: ignore[attr-defined]
        for sample in metric.samples
    }


def test_capture_total_labels() -> None:
    metrics.capture_total.labels(source_type="text", outcome="ok").inc()
    metrics.capture_total.labels(source_type="voice", outcome="error").inc()
    # Smoke: no exception means label cardinality is honoured. Counter._name
    # intentionally stores the base name without Prometheus' exported _total.
    assert "mnemo_capture_total" in _sample_names(metrics.capture_total)


def test_query_total_outcomes() -> None:
    for outcome in ("ok", "empty", "error"):
        metrics.query_total.labels(outcome=outcome).inc()


def test_llm_tokens_directions() -> None:
    metrics.llm_tokens_total.labels(direction="prompt", provider="openrouter").inc(10)
    metrics.llm_tokens_total.labels(direction="completion", provider="ollama").inc(5)


def test_worker_task_total_labels() -> None:
    metrics.worker_task_total.labels(actor="process_text_note", outcome="ok").inc()
    metrics.worker_task_total.labels(actor="trigger_n8n_workflow", outcome="error").inc()


def test_webhook_total_labels() -> None:
    for outcome in ("accepted", "duplicate", "rejected", "error"):
        metrics.webhook_total.labels(event="note-ready", outcome=outcome).inc()


def test_queue_depth_is_a_gauge() -> None:
    metrics.queue_depth.set(0)
    metrics.queue_depth.set(42)
    metrics.queue_depth.set(-1)  # legal for a Gauge (e.g., placeholder)
